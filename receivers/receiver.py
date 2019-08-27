class Receiver(object):

    NAME = "receiver"

    def __init__(self, cluster_name, team, images):

        self.cluster_name = cluster_name
        self.team = team
        self.warning_image = images['warning']
        self.progress_image = images['progress']
        self.ok_image = images['ok']

        self.rollouts = {}

        self.channel = None

        self._ROLLOUT_COMPLETE = 1
        self._ROLLOUT_PROGRESSING = 2
        self._ROLLOUT_DEGRADED = 3
        self._ROLLOUT_FAILURE = 4
        self._ROLLOUT_UNKNOWN = 5

    def rollout_complete(self, status):
        return status == self._ROLLOUT_COMPLETE

    def rollout_progressing(self, status):
        return status == self._ROLLOUT_PROGRESSING

    def rollout_degraded(self, status):
        return status == self._ROLLOUT_DEGRADED

    def rollout_failure(self, status):
        return status == self._ROLLOUT_FAILURE

    def rollout_unknown(self, status):
        return status == self._ROLLOUT_UNKNOWN

    def pipeline_url(self, deployment):
        annotations = deployment.metadata.annotations
        return annotations.get("kube-lookout/pipeline-url")

    def ingress_url(self, deployment):
        annotations = deployment.metadata.annotations
        return annotations.get("kube-lookout/ingress-url")

    # See https://kubernetes.io/docs/concepts/workloads/controllers/deployment/
    def _rollout_status(self, replicas, ready_replicas, conditions):
        if not conditions:
            return self._ROLLOUT_UNKNOWN, "", ""

        for condition in conditions:

            if condition.status == 'False':
                return (self._ROLLOUT_DEGRADED, condition.reason,
                        condition.message)

            if condition.type in ('Available', 'Progressing'):
                if replicas == ready_replicas:
                    return (self._ROLLOUT_COMPLETE, condition.reason,
                            condition.message)

                if condition.reason == 'MinimumReplicasUnavailable':
                    return (self._ROLLOUT_DEGRADED,
                            condition.reason,
                            condition.message)

                else:
                    return (self._ROLLOUT_PROGRESSING,
                            condition.reason,
                            condition.message)

            if condition.type == 'ReplicaFailure':
                return (self._ROLLOUT_FAILURE, condition.reason,
                        condition.message)

    def _handle_deployment_change(self, deployment):
        metadata = deployment.metadata
        deployment_key = f"{metadata.creation_timestamp}/{metadata.namespace}/{metadata.name}"

        reason = ""

        replicas = deployment.spec.replicas or 0
        ready_replicas = deployment.status.ready_replicas or 0

        rollout_status, reason, message = \
            self._rollout_status(replicas,
                                 ready_replicas,
                                 deployment.status.conditions)

        if self.rollout_unknown(rollout_status):
            return

        blocks = self._generate_deployment_message(deployment, replicas,
                                                   ready_replicas, reason,
                                                   message, rollout_status)

        if deployment_key not in self.rollouts:
            self.rollouts[deployment_key] = self._send_message(
                channel=self.channel, data=blocks)
        else:
            self._send_message(
                channel=self.rollouts[deployment_key][1],
                message_id=self.rollouts[deployment_key][0], data=blocks)

        if self.rollout_complete(rollout_status):
            self.rollouts.pop(deployment_key)

    def _should_handle(self, team, receiver):
        return True if self.team == team and self.NAME == receiver \
            else False

    def handle_event(self, team, receiver, deployment):
        if self._should_handle(team, receiver):
            print("Receiver '%s' handling event for team '%s'" % (receiver,
                                                                  team))

            self._handle_deployment_change(deployment)

class Receiver(object):

    NAME = "receiver"

    def __init__(self, cluster_name, team, images):

        self.cluster_name = cluster_name
        self.team = team
        self.warning_image = images['warning']
        self.progress_image = images['progress']
        self.ok_image = images['ok']

        self.rollouts = {}
        self.previous_rollout_status = {}
        self.previous_rollout_generation = {}

        self.channel = None
        
        self._ROLLOUT_CREATED = 1
        self._ROLLOUT_COMPLETE = 2
        self._ROLLOUT_PROGRESSING = 3
        self._ROLLOUT_DEGRADED = 4
        self._ROLLOUT_FAILURE = 5
        self._ROLLOUT_UNKNOWN = 6


    def rollout_created(self, status):
        return status == self._ROLLOUT_CREATED

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
    def _rollout_status(self, conditions,
                        wanted_replicas,
                        updated_replicas,
                        unavailable_replicas):

        if not conditions:
            return self._ROLLOUT_UNKNOWN, "", ""
            
        last_condition = conditions[-1]

        print("%s - %s - %s" % (last_condition.type, last_condition.message, last_condition.reason))

        if last_condition.type == 'ReplicaFailure':
            return (self._ROLLOUT_FAILURE, last_condition.reason,
                    last_condition.message)

        if last_condition.reason == 'NewReplicaSetCreated':
            return (self._ROLLOUT_CREATED,
                    last_condition.reason,
                    last_condition.message)

        if last_condition.reason == 'NewReplicaSetAvailable':
            return (self._ROLLOUT_COMPLETE,
                    last_condition.reason,
                    last_condition.message)

        if last_condition.reason == 'MinimumReplicasUnavailable':
            if not unavailable_replicas and (wanted_replicas == updated_replicas):
                return (self._ROLLOUT_COMPLETE,
                    last_condition.reason,
                    last_condition.message)
            else:
                return (self._ROLLOUT_DEGRADED,
                        last_condition.reason,
                        last_condition.message)

        else:
            return (self._ROLLOUT_PROGRESSING,
                    last_condition.reason,
                    last_condition.message)

    def _handle_deployment_change(self, deployment):
        metadata = deployment.metadata
        deployment_key = f"{metadata.namespace}/{metadata.name}"

        wanted_replicas = deployment.spec.replicas or 0
        updated_replicas = deployment.status.updated_replicas or 0
        ready_replicas = deployment.status.ready_replicas or 0
        unavailable_replicas = deployment.status.unavailable_replicas or 0
        available_new_replicas = updated_replicas - unavailable_replicas

        generation = deployment.status.observed_generation or 0

        latest_condition_message = "%s" % (deployment.status.conditions[-1].message)

        # If this deployment generation has already completed, then skip related events
        # events.
        if generation <= self.previous_rollout_generation.get(deployment_key, 0):
            return

        # If we've already sent a message for this deployment with the same status,
        # skip it.
        if self.previous_rollout_status.get(deployment_key) == latest_condition_message:
            if wanted_replicas != updated_replicas:
                return

        self.previous_rollout_status[deployment_key] = latest_condition_message

        print(deployment.status)
        print(latest_condition_message)
        print(self.previous_rollout_status)

        rollout_status, reason, message = \
            self._rollout_status(deployment.status.conditions,
                                 wanted_replicas,
                                 updated_replicas,
                                 unavailable_replicas)

        # Skip any unknown rollout status
        if self.rollout_unknown(rollout_status):
            return

        # Generate message
        blocks = self._generate_deployment_message(deployment, reason, wanted_replicas,
                                                   ready_replicas,
                                                   available_new_replicas,
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
            self.previous_rollout_status.pop(deployment_key)
            self.previous_rollout_generation[deployment_key] = generation


    def _should_handle(self, team, receiver):
        return True if self.team == team and self.NAME == receiver \
            else False

    def handle_event(self, team, receiver, deployment):
        if self._should_handle(team, receiver):
            self._handle_deployment_change(deployment)

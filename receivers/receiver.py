ROLLOUT_COMPLETE = 1
ROLLOUT_PROGRESSING = 2
ROLLOUT_DEGRADED = 3
ROLLOUT_FAILURE = 4
ROLLOUT_UNKNOWN = 5


class Receiver(object):

    NAME = "receiver"

    def __init__(self, cluster_name, team, images):

        self.cluster_name = cluster_name
        self.team = team
        self.warning_image = images['warning']
        self.ok_image = images['ok']
        self.progress_image = images['progress']

        self.rollouts = {}

        self.channel = None

    # See https://kubernetes.io/docs/concepts/workloads/controllers/deployment/
    # Type=Available with Status=True: means that your Deployment has minimum availability
    # Type=Progressing with Status=True means that your Deployment is either in the middle
    #     of a rollout and it is progressing or that it has successfully
    # Reason=NewReplicaSetAvailable means that the Deployment is complete
    #
    #
    # Returns:
    #   Progressing 
    #   Failure
    #   Success
    def _rollout_status(self, replicas, ready_replicas, conditions):
        if not conditions:
            return ROLLOUT_UNKNOWN, "", ""

        for condition in conditions:
            if condition.type == "ReplicaFailure":
                rollout = ROLLOUT_FAILURE
                reason = condition.reason
                message = conditoin.message
                return (ROLLOUT_FAILURE, conditoin.reason, conditoin.message)
            if condition.type == "Available" and condition.reason == "MinimumReplicasUnAvailable":
                return (ROLLOUT_DEGRADED, condition.reason, condition.message)
            if condition.type == "Progressing":
                if condition.status == True:
                    if condition.reason == "NewReplicaSetAvailable":
                        return (ROLLOUT_COMPLETE, condition.reason, condition.message)
                    else:
                        return (ROLLOUT_PROGRESSING, condition.reason, condition.message)

        return ROLLOUT_UNKNOWN, "", ""

    def _handle_deployment_change(self, deployment):
        metadata = deployment.metadata
        deployment_key = f"{metadata.creation_timestamp}/{metadata.namespace}/{metadata.name}"

        reason = "" 

        replicas = deployment.status.replicas or 0
        ready_replicas = deployment.status.ready_replicas or 0

        print(deployment.status)
        rollout_status, reason, message = self._rollout_status(replicas, ready_replicas, deployment.status.conditions)
        print(rollout_status, reason, message)

        return 

        if deployment_key not in self.rollouts: 

            blocks = self._generate_deployment_rollout_message(deployment)
            self.rollouts[deployment_key] = self._send_message(
                channel=self.channel, data=blocks)

        elif rollout_status == ROLLOUT_DEGRADED:
            blocks = self._generate_deployment_degraded_message(deployment)
            self._send_message(
                channel=self.rollouts[deployment_key][1],
                message_id=self.rollouts[deployment_key][0], data=blocks)

        elif rollout_status == ROLLOUT_PROGRESSING:
            blocks = self._generate_deployment_not_degraded_message(deployment)

            self._send_message(
                channel=self.rollouts[deployment_key][1],
                message_id=self.rollouts[deployment_key][0], data=blocks)

        elif rollout_status == ROLLOUT_COMPLETE:
            blocks = self._generate_deployment_not_degraded_message(deployment)
            blocks = self._generate_deployment_rollout_message(deployment, True)
            self._send_message(
                channel=self.rollouts[deployment_key][1],
                message_id=self.rollouts[deployment_key][0], data=blocks)

            self.rollouts.pop(deployment_key)
        elif rollout_status == ROLLOUT_FAILURE:
            print("FAILURE")

    def _should_handle(self, team, receiver):
        return True if self.team == team and self.NAME == receiver \
            else False

    def handle_event(self, team, receiver, deployment):
        if self._should_handle(team, receiver):
            print("Receiver '%s' handling event for team '%s'" % (receiver,
                                                                  team))

            self._handle_deployment_change(deployment)

from copy import copy
import utils
import slack

from .receiver import Receiver


class SlackReceiver(Receiver):

    NAME = "slack"

    template = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": ""
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": ""
            },
            "accessory": {
                "type": "image",
                "image_url": "",
                "alt_text": "status image"
            }
        }
    ]

    def __init__(self, cluster_name, team, images, slack_key, channel):
        super().__init__(cluster_name, team, images)
        self.slack_client = None
        self.team = team
        self.slack_key = slack_key
        self.channel = channel

        print("configured slack-receiver for %s/%s" % (self.team,
              self.channel))

    def _send_message(self, data, channel=None, message_id=None):
        if self.slack_client is None:
            self.slack_client = slack.WebClient(
                self.slack_key)

        if message_id is None:
            response = self.slack_client.chat_postMessage(channel=channel,
                                                          blocks=data)
        else:
            response = self.slack_client.chat_update(channel=channel,
                                                     ts=message_id,
                                                     blocks=data)

        return response.data['ts'], response.data['channel']

    def _generate_deployment_message(self, deployment, replicas,
                                     ready_replicas, reason, message,
                                     rollout_status):

        block = copy(self.template)
        header = f"*{self.cluster_name} " \
            f"{deployment.metadata.namespace}/{deployment.metadata.name}" \
            f" is rolling out an update.*"
        message = ''
        for container in deployment.spec.template.spec.containers:
            message += f"Container {container.name} has image " \
                f"_ {container.image} _\n"
        message += "\n"
        message += f"{ready_replicas} replicas " \
            f"updated out of " \
            f"{replicas}\n\n"

        message += utils.generate_progress_bar(ready_replicas, replicas)

        block[0]['text']['text'] = header
        block[1]['text']['text'] = message

        if self.rollout_complete(rollout_status):
            block[1]['accessory']['image_url'] = self.ok_image
        elif self.rollout_progressing(rollout_status):
            block[1]['accessory']['image_url'] = self.progress_image
        elif self.rollout_degraded(rollout_status):
            block[1]['accessory']['image_url'] = self.warning_image
        else:
            block[1]['accessory']['image_url'] = self.warning_image

        return block

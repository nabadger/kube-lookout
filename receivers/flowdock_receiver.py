from copy import copy
import flowdock

from .receiver import Receiver


class FlowdockReceiver(Receiver):

    NAME = "flowdock"

    template = {
        "author": {
            "name": "KubeLookout",
        },
        "title": "Title",
        "external_thread_id": "Item-1",
        "thread": {
            "title": "thread-title",
            "body": "body-html",
            "external_url": "",
            "status": {
                "value": "Deploying...",
                "color": "red",
            }
        }
    }

    def __init__(self, cluster_name, team, images, flowdock_token):
        super().__init__(cluster_name, team, images)
        self.flowdock_client = None
        self.flowdock_token = flowdock_token
        self.channel = "fake-not-used-yet-as-tied-to-token"

        print("configured flow-receiver for %s" % (self.team))

    def _send_message(self, data, channel=None, message_id=None):
        # FIXME: channel not used here
        item_id = data.get('resource_uid')
        author = data.get('author')
        title = "deploy monitor"
        item = data.get("thread")
        data['external_thread_id'] = item_id

        if self.flowdock_client is None:
            self.flowdock_client = flowdock.connect(
                flow_token=self.flowdock_token)

        if message_id is None:
            # Send a new message
            self.flowdock_client.present(item_id, author=author,
                                         title=title,
                                         body=item['body'],
                                         thread=item)
            # FIXME - this is not ideal
            return item_id, item_id

        # Update exiting message
        self.flowdock_client.present(item_id, author=author,
                                     title=title,
                                     body=item['body'],
                                     thread=item)

        # FIXME - this is not ideal
        return item_id, item_id

    def _generate_deployment_message(self, deployment, replicas,
                                     ready_replicas, reason, message,
                                     rollout_status):
        data = copy(self.template)

        replica_status = f"{ready_replicas}/{replicas}"
        message = f"{reason} - {message}</br>"
        message += f"Number of replicas - <b>{ready_replicas}/{replicas}</b></br>"

        if self.rollout_complete(rollout_status):
            ingress_url = self.ingress_url(deployment)
            if ingress_url:
                message += f"Deployed to: <a href=\"{ingress_url}\">{ingress_url}</a></br>"

        header = f"[{replica_status}] [{self.cluster_name.upper()}]" \
            f" [{deployment.metadata.namespace}/{deployment.metadata.name}]"

        data["thread"]["title"] = header
        data["thread"]["body"] = message
        data["thread"]["external_url"] = self.pipeline_url(deployment)

        if self.rollout_complete(rollout_status):
            data["thread"]["status"]["value"] = 'DEPLOYED'
            data["thread"]["status"]["color"] = 'green'
        elif self.rollout_progressing(rollout_status):
            data["thread"]["status"]["value"] = 'PROGRESSING'
            data["thread"]["status"]["color"] = 'blue'
        elif self.rollout_degraded(rollout_status):
            data["thread"]["status"]["value"] = 'DEGRADED'
            data["thread"]["status"]["color"] = 'red'
        else:
            print("Hmm unknown status")
            # FIXME
        data['resource_uid'] = deployment.metadata.uid

        return data


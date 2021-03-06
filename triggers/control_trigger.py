import time
import json
import redis
import sys
from .trigger import Trigger



from logger.Logger import Logger, LOG_LEVEL


class ControlTrigger(Trigger):

    def __init__(
            self, main_thread_running, system_ready, name='ControlTrigger',
            key=None, source=None, thresholds=None, topic="controls",
            trigger_active=None, frequency='once', actions=[],
            group=None, redis_conn=None, sequences=[]):
        super().__init__(
            main_thread_running,
            system_ready,
            name=name,
            key=key,
            source=source,
            thresholds=thresholds,
            trigger_active=trigger_active,
            frequency=frequency,
            actions=actions,
            trigger_interval=0.5,
            group=group,
            sequences=sequences
        )
        self.topic = topic.replace(" ",
                                   "_").lower() if topic is not None else "controls"

        try:
            self.r = redis_conn if redis_conn is not None else redis.Redis(
                host='127.0.0.1', port=6379)
        except KeyError:
            self.r = redis.Redis(host='127.0.0.1', port=6379)
        return

    def init_trigger(self):
        # Initialize the trigger here (i.e. set listeners or create cron jobs)
        # Pubsub Listeners
        self.pubsub = self.r.pubsub()
        self.pubsub.subscribe(**{self.topic: self.handle_event})
        pass

    def check(self):
        while self.main_thread_running.is_set():
            if self.system_ready.is_set():
                super().check()
                self.pubsub.get_message()
                # self.trigger_active.clear()
                time.sleep(self.trigger_interval)
            else:
                time.sleep(2)
        return

    def handle_event(self, message):
        data = message['data']
        if data is not None:
            decoded_message = super().decode_event_data(data)

            try:
                if decoded_message['event'] == 'ControlUpdate':
                    control_value = self.parse_control_data(
                        decoded_message["data"]
                    )
                    if super().evaluate_thresholds(control_value):
                        self.trigger_active.set()
                        if self.previous_state != self.trigger_active.is_set():
                            super().trigger(decoded_message['event'])
                        else:
                            if self.frequency == 'many':
                                super().trigger(decoded_message['event'])
                    else:
                        self.trigger_active.clear()

            except:
                Logger.log(
                    LOG_LEVEL["error"],
                    'Error During Trigger Actions {0}'.format(self.key)
                )
        self.previous_state = self.trigger_active.is_set()

    def parse_control_data(self, data):
        parsed_data = data.get(self.source, None)
        return parsed_data

    def shutdown(self):
        self.pubsub.close()
        return

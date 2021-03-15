""" 
    LCD Character Displays Extension
    Displays are very useful to output
    messages from the system. Character
    displays supported 16x2 and 20x4.
"""
import re
import time
import json
from mudpi.utils import decode_event_data
from mudpi.logger.Logger import Logger, LOG_LEVEL
from mudpi.extensions import Component, BaseExtension


NAMESPACE = 'char_display'

class Extension(BaseExtension):
    namespace = NAMESPACE
    update_interval = 0.5

    def init(self, config):
        self.config = config[self.namespace]
        
        self.manager.init(self.config)

        self.manager.register_component_actions('show', action='show')
        self.manager.register_component_actions('clear', action='clear')
        self.manager.register_component_actions('clear_queue', action='clear_queue')
        self.manager.register_component_actions('next_message', action='next_message')
        self.manager.register_component_actions('turn_on_backlight', action='turn_on_backlight')
        self.manager.register_component_actions('turn_off_backlight', action='turn_off_backlight')
        return True


class CharDisplay(Component):
    """ Base CharDisplay
        Base Character Display Class
    """

    # Current message being displayed
    current_message = ''

    # Check current_message to display once / prevent flickers
    cached_message = {
        'message': '',
        'duration': 3
    }

    # Bool if message should be rotated
    message_expired = True

    # Queue of messages to display
    queue = [] #queue.Queue()

    # Duration tracking
    _duration_start = time.perf_counter()

    @property
    def id(self):
        """ Unique id or key """
        return self.config.get('key')

    @property
    def name(self):
        """ Friendly name of control """
        return self.config.get('name') or f"{self.id.replace('_', ' ').title()}"

    @property
    def state(self):
        """ Return state of the display """
        return self.current_message

    @property
    def default_duration(self):
        """ Default message display duration """
        return int(self.config.get('default_duration', 5))

    @property
    def max_duration(self):
        """ Message max display duration to prevent display lock """
        return int(self.config.get('max_duration', 60))

    @property
    def message_limit(self):
        """ Max number of messages before overwriting """
        return int(self.config.get('message_limit', 20))
    
    @property
    def topic(self):
        """ Max number of messages before overwriting """
        return str(self.config.get('topic', f'{NAMESPACE}/{self.id}'))

    @property
    def duration(self):
        """ Return how long the current state has been applied in seconds """
        self._current_duration = time.perf_counter() - self._duration_start
        return round(self._current_duration, 4)


    """ Actions """
    def show(self, data=None): 
        """ Show a message on the screen """
        pass

    def clear(self, data=None):
        """ Clear the display screen """
        pass

    def turn_on_backlight(self, data=None):
        """ Turn the backlight on """
        pass

    def turn_off_backlight(self, data=None):
        """ Turn the backlight on """
        pass

    def clear_queue(self, data=None):
        """ Clear the message queue """
        self.queue = []
        Logger.log(LOG_LEVEL["debug"],
                   f'Cleared the Message Queue for {self.id}')

    def next_message(self, data={}):
        """ Advances to the next message """
        self.message_expired = True


    """ Methods """
    def init(self):
        """ Setup the display to listen for events """
        self.mudpi.events.subscribe(self.topic, self.handle_event)

    def update(self):
        """ Check if messages need to display from queue """
        if self.mudpi.is_prepared:
            if self.duration > self.cached_message['duration'] + 1:
                self.message_expired = True

            if self.message_expired:
                # Get first time message after clear
                self.cached_message = self.get_next_message()

            if self.current_message != self.cached_message.get('message', ''):
                self.clear()
                time.sleep(0.004) # time to finish clear
                self.show(self.cached_message)
                self.reset_duration()
                # store message to only display once and prevent flickers
                self.current_message = self.cached_message['message']
        else:
            # System not ready
            self.reset_duration()

    def add_message(self, data={}):
        """ Add message to display queue """
        message = data.get('message', '')
        duration = data.get('duration', self.default_duration)
        if duration > self.max_duration:
            duration = self.max_duration

        # Replace any codes such as [temperature] with a value
        # found in the state manager. TODO: add templates instead
        short_codes = re.findall(r'\[(.*?) *\]', message)

        for code in short_codes:
            data = self.mudpi.states.get(code)

            if data is None:
                data = ''

            else:
                try:
                    data = json.loads(state.state)
                except Exception:
                    data = ''
            message = message.replace('[' + code + ']', str(data))

        new_message = {
            "message": message.replace("\\n", "\n"),
            "duration": duration
        }

        if len(self.queue) >= self.message_limit:
            self.queue.pop(0)

        self.queue.append(new_message)

        _event = {'event': 'MessageQueued', 'data': new_message}
        self.mudpi.events.publish(NAMESPACE, _event)
        return

    def get_next_message(self):
        """ Get the next message from queue """
        if len(self.queue) > 0:
            self.message_expired = False
            self.reset_duration()
            return self.queue.pop(0)
        return {'message': '', 'duration': self.default_duration}

    def reset_duration(self):
        """ Reset the duration of the current state """
        self._duration_start = time.perf_counter()
        return self._duration_start

    def handle_event(self, event):
        """ Handle events from event system """
        data = event['data']
        if data is not None:
            _event = decode_event_data(data)
            try:
                if _event['event'] == 'Message':
                    if _event.get('data', None):
                        _duration = _event['data'].get('duration', self.default_duration)
                        _message = _event['data'].get('message', '')
                        self.add_message(_message, int(_duration))
                elif _event['event'] == 'Clear':
                    self.clear()
                elif _event['event'] == 'ClearQueue':
                    self.clear_queue()
            except Exception:
                Logger.log(LOG_LEVEL["error"],
                           f'Error Handling Event for {self.id}')
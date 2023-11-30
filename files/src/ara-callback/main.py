# source: https://gist.githubusercontent.com/phemmer/8ee4ea0ebf1b389050ce4a2bd78c66d6/raw/9dd048488fb119caeff0f45c196e5d3e0e231255/ara_wrapper.py
#         https://github.com/ansible-community/ara/issues/171#issuecomment-1302863591

import queue
import threading

from ara.plugins.callback.ara_default import (
    CallbackModule as ARACallbackModule,
    DOCUMENTATION,
)


class CallbackModule(ARACallbackModule):
    def thread_worker(self):
        while True:
            event = self.thread_queue.get()
            if event is None:
                self.thread_queue.task_done()
                break

            event[0](*event[1], **event[2])

            self.thread_queue.task_done()

    def thread_start(self):
        self.thread_queue = queue.Queue()
        self.thread = threading.Thread(target=self.thread_worker)
        self.thread.start()

    def thread_stop(self):
        if not self.thread:
            return
        self.thread_queue.put(None)
        self.thread.join()

    def v2_playbook_on_start(self, *args, **kwargs):
        self.thread_start()

        self.thread_queue.put((super().v2_playbook_on_start, args, kwargs))

    def v2_playbook_on_stats(self, *args, **kwargs):
        self.thread_queue.put((super().v2_playbook_on_stats, args, kwargs))

        self.thread_stop()

    def v2_playbook_on_play_start(self, *args, **kwargs):
        self.thread_queue.put((super().v2_playbook_on_play_start, args, kwargs))

    def v2_playbook_on_handler_task_start(self, *args, **kwargs):
        self.thread_queue.put((super().v2_playbook_on_handler_task_start, args, kwargs))

    def v2_playbook_on_task_start(self, *args, **kwargs):
        self.thread_queue.put((super().v2_playbook_on_task_start, args, kwargs))

    def v2_runner_on_start(self, *args, **kwargs):
        self.thread_queue.put((super().v2_runner_on_start, args, kwargs))

    def v2_runner_on_ok(self, *args, **kwargs):
        self.thread_queue.put((super().v2_runner_on_ok, args, kwargs))

    def v2_runner_on_unreachable(self, *args, **kwargs):
        self.thread_queue.put((super().v2_runner_on_unreachable, args, kwargs))

    def v2_runner_on_failed(self, *args, **kwargs):
        self.thread_queue.put((super().v2_runner_on_failed, args, kwargs))

    def v2_runner_on_skipped(self, *args, **kwargs):
        self.thread_queue.put((super().v2_runner_on_skipped, args, kwargs))

    def v2_runner_item_on_ok(self, *args, **kwargs):
        self.thread_queue.put((super().v2_runner_item_on_ok, args, kwargs))

    def v2_runner_item_on_failed(self, *args, **kwargs):
        self.thread_queue.put((super().v2_runner_item_on_failed, args, kwargs))

    def v2_runner_item_on_skipped(self, *args, **kwargs):
        self.thread_queue.put((super().v2_runner_item_on_skipped, args, kwargs))

    def v2_playbook_on_include(self, *args, **kwargs):
        self.thread_queue.put((super().v2_playbook_on_include, args, kwargs))

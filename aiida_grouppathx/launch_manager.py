"""
Manager for keep X number of active jobs to run at a time, which is useful when
- There are lots of jobs to run
- The local computer cannot handle all the jobs at once
- The remove cluster has limit on the number of jobs that can be queued at a time
"""

import time
from typing import Callable, Optional

from .pathx import GroupPathX, only_nodes_with_cache


class GroupLauncher:
    def __init__(
        self,
        target_gp: GroupPathX,
        max_concurrent: int,
        callback: Callable,
        source_gp: Optional[GroupPathX] = None,
        log_to_stdout: bool = True,
        force: bool = False,
        logfile: Optional[str] = None,
        source_key_obj_pairs: Optional[list] = None,
        sleep_seconds: float = 120,
    ):
        """
        Configure the launcher to launch jobs from a source group or a list of source objects / groupath.

        :param target_gp: The group path to store the launched jobs to.
        :param max_concurrent: The maximum number of concurrent jobs to run.
        :param callback: The callback function to launch a job. It should take two arguments:
          the object to launch and an identifier for the object.
          It should return a tuple of the launched node and the key for path it should be stored inside the target
          group path.
        :param source_gp: The group path to get jobs from (optional), the key and the object pairs will be taken
          from this group path.
        :param log_to_stdout: Whether to log to stdout.
        :param force: Whether to force the launch of the job.
        :param logfile: The file to log to.
        :param source_key_obj_pairs: A list of key and object pairs to launch jobs from, instead of a source group path.
        :param sleep_seconds: The number of seconds to sleep before checking the status of the jobs.
        """
        self.target_group = target_gp
        self.source_gp = source_gp
        self.source_key_obj_pairs = source_key_obj_pairs
        self.max_concurrent = max_concurrent
        self.callback = callback
        self.sleep_seconds = sleep_seconds
        self.log_to_stdout = log_to_stdout
        self.force = force
        self.logfile = logfile
        self.log_to_stdout = log_to_stdout
        assert self.source_gp is not None or self.source_key_obj_pairs is not None

    def sleep(self):
        """Sleep for a while before checking the status of the jobs."""
        time.sleep(self.sleep_seconds)

    def launch_loop(self):
        """The main launch for launch underlying jobs"""
        obj_list = self.source_key_obj_pairs
        if obj_list is None:
            with only_nodes_with_cache(self.source_gp):
                obj_list = [(path.key, path.get_node()) for path in self.source_gp]

        while True:
            tmp = time.time()
            with only_nodes_with_cache(self.source_gp):
                launched = [[path.key, path.get_node()] for path in self.target_group]
            launched_keys = next(zip(*launched))
            n_running = sum([1 for key, node in launched if not node.is_finished])
            self.report(f'Total number of running jobs: {n_running}')
            job_left = [[key, node] for key, node in obj_list if key not in launched_keys]
            if len(job_left) == 0:
                print('No job to launch left - stopping')
                break
            self.report(f'Total number of jobs to run : {len(job_left)}')
            tmp = time.time() - tmp
            self.report(f'Time elapsed to gather jobs: {tmp:.2f} seconds')
            nfree = self.max_concurrent - n_running
            if nfree > 0:
                self.report(f'Launching {nfree} jobs...')
                # Launch jobs
                for key, job in job_left[:nfree]:
                    node, label = self.callback(job, key)
                    self.target_group.add_node(node, label, force=self.force)
                self.report(f'Launched {nfree} jobs...')
            self.sleep()

    def report(self, message):
        """Report the status of the jobs."""
        if self.log_to_stdout:
            print(message)
        if self.logfile is not None:
            with open(self.logfile, 'a') as fh:
                print(message, file=fh)

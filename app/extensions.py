from apscheduler.schedulers.background import BackgroundScheduler

class Scheduler:
    def __init__(self):
        self.scheduler = None
    
    def init_app(self, app):
        self.scheduler = BackgroundScheduler({
            'apscheduler.timezone': 'UTC',
            'apscheduler.job_defaults.max_instances': 3
        })
        self.scheduler.start()

scheduler = Scheduler()
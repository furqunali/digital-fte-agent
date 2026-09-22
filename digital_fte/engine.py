from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .models import TaskResult
from .parser import parse_task


class TaskEngine:
    def __init__(self,vault:Path):
        self.vault=vault; self.inbox=vault/"Inbox"; self.dashboard=vault/"Dashboard"; self.logs=vault/"Logs"
        for p in (self.inbox,self.dashboard,self.logs): p.mkdir(parents=True,exist_ok=True)
    def process(self,path:Path)->TaskResult:
        started=datetime.now(timezone.utc).isoformat(); task=parse_task(path)
        output=self.dashboard/f"{task.task_id}.md"; log=self.logs/f"{task.task_id}.log"
        try:
            output.write_text(f"# Task Result: {task.title}\\n\\nStatus: completed\\n\\n## Received Instruction\\n\\n{task.body}\\n",encoding="utf-8")
            status="completed"; error=None
        except Exception as exc:
            status="failed"; error=str(exc)
        finished=datetime.now(timezone.utc).isoformat()
        log.write_text(f"task_id={task.task_id}\\nstatus={status}\\nstarted_at={started}\\nfinished_at={finished}\\nerror={error or ''}\\n",encoding="utf-8")
        return TaskResult(task.task_id,status,output,log,started,finished,error)

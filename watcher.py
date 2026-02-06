import time
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class NewTaskHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith(".md"):
            filename = os.path.basename(event.src_path)
            print(f"\n[!] 🔔 New Instruction Detected: {filename}")
            
            # Simulation: Instead of calling Claude EXE, we simulate the thought process
            print(f"[!] 🤖 Processing logic for: {filename}...")
            time.sleep(2)
            
            output_path = "./AI_Employee_Vault/Dashboard/SocialPlan.md"
            with open(output_path, "w") as f:
                f.write("# Social Media Growth Plan\n\n1. Post daily updates.\n2. Engage with community.\n3. Audit weekly revenue.")
            
            print(f"[!] ✅ Success! Result saved in Dashboard/SocialPlan.md")

if __name__ == "__main__":
    path_to_watch = "./AI_Employee_Vault/Inbox"
    if not os.path.exists(path_to_watch): os.makedirs(path_to_watch)
    event_handler = NewTaskHandler()
    observer = Observer()
    observer.schedule(event_handler, path_to_watch, recursive=False)
    print("--------------------------------------------------")
    print("🤖 DIGITAL FTE SENTINEL (SIMULATED MODE) ACTIVE")
    print("--------------------------------------------------")
    observer.start()
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

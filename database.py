from pymongo import MongoClient
from datetime import datetime
import os

MONGO_URI = os.getenv('MONGO_URI')
if not MONGO_URI:
    raise ValueError("MONGO_URI environment variable is not set.")
DATABASE_NAME = "TaskSphere_bot"
COLLECTION_NAME = "tasks"

client = MongoClient(MONGO_URI)
db = client[DATABASE_NAME]
tasks_collection = db[COLLECTION_NAME]

def create_list(list_name):
    if tasks_collection.find_one({"List": list_name}):
        return False
    tasks_collection.insert_one({"List": list_name, "Tasks": []})
    return True

def delete_list(list_name):
    result = tasks_collection.delete_one({"List": list_name})
    return result.deleted_count > 0

def add_task(list_name, task_name, assigned_to, deadline):
    list_exists = tasks_collection.find_one({"List": list_name})
    if not list_exists:
        return "ListNotFound"

    task = {
        "Task Name": task_name,
        "Assigned To": assigned_to,
        "Deadline": deadline,
        "Status": "In Progress",
        "Completion Time": None
    }
    tasks_collection.update_one({"List": list_name}, {"$push": {"Tasks": task}})
    return True

def delete_task(list_name, task_name):
    result = tasks_collection.update_one(
        {"List": list_name},
        {"$pull": {"Tasks": {"Task Name": task_name}}}
    )
    return result.modified_count > 0

def update_task_status(task_name, new_status):
    result = tasks_collection.update_one(
        {"Tasks.Task Name": task_name},
        {"$set": {"Tasks.$.Status": new_status, "Tasks.$.Completion Time": datetime.now() if new_status.lower() == "done" else None}}
    )
    return result.modified_count > 0

def get_tasks(list_name=None, username=None):
    query = {}
    if list_name:
        query = {"List": list_name}
    if username:
        query = {"Tasks.Assigned To": username}
    
    results = tasks_collection.find(query)
    tasks = []
    for result in results:
        for task in result.get("Tasks", []):
            if username and task["Assigned To"] != username:
                continue
            task["List"] = result["List"]
            tasks.append(task)
    return tasks

def list_all_lists():
    return [doc["List"] for doc in tasks_collection.find({}, {"List": 1, "_id": 0})]
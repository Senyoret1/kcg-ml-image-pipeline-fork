from fastapi import Request, HTTPException, APIRouter, Response, Query, status
from datetime import datetime, timedelta
import math
import random
import pymongo
from utility.minio import cmd
from orchestration.api.mongo_schemas import  ActiveLearningPolicy
from .api_utils import PrettyJSONResponse
import os
from datetime import datetime, timezone
from typing import List
from io import BytesIO
import json

router = APIRouter()


@router.post("/active-learning-queue/add-policy")
def add_policy(request: Request, policy_data: ActiveLearningPolicy):
    # Find the maximum active_learning_policy_id in the collection
    last_entry = request.app.active_learning_policies_collection.find_one({}, sort=[("active_learning_policy_id", -1)])
    new_policy_id = last_entry["active_learning_policy_id"] + 1 if last_entry else 0

    # Ensure that the policy does not already exist
    if request.app.active_learning_policies_collection.find_one({"active_learning_policy": policy_data.active_learning_policy}):
        raise HTTPException(status_code=400, detail="Policy already exists")

    # Add the new policy
    policy_data.active_learning_policy_id = new_policy_id
    policy_data.creation_time = datetime.now(timezone.utc).isoformat()
    request.app.active_learning_policies_collection.insert_one(policy_data.to_dict())

    return {"status": "success", "message": "New active learning policy added.", "active_learning_policy_id": new_policy_id}


@router.put("/active-learning-queue/update-policy")
def update_policy(request: Request, policy_id: int, policy_update: ActiveLearningPolicy):
    # Ensure that the policy exists
    existing_policy = request.app.active_learning_policies_collection.find_one({"active_learning_policy_id": policy_id})
    if not existing_policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    # Update the policy
    update_data = policy_update.dict(exclude_unset=True)
    request.app.active_learning_policies_collection.update_one({"active_learning_policy_id": policy_id}, {"$set": update_data})

    return {"status": "success", "message": "Active learning policy updated.", "active_learning_policy_id": policy_id}


@router.get("/active-learning-queue/list-policies", response_class=PrettyJSONResponse)
def list_active_learning_policies(request: Request) -> List[ActiveLearningPolicy]:
    # Retrieve all active learning policies from the collection
    policies_cursor = request.app.active_learning_policies_collection.find({})

    # Convert the cursor to a list of ActiveLearningPolicy objects
    policies = [ActiveLearningPolicy(**policy) for policy in policies_cursor]

    return policies


@router.delete("/active-learning-queue/remove-policies")
def delete_active_learning_policy(request: Request, active_learning_policy_id: int = None):
    if active_learning_policy_id is not None:
        # Check if any queue pairs are using this policy
        if request.app.active_learning_queue_pairs_collection.find_one({"active_learning_policy_id": active_learning_policy_id}):
            raise HTTPException(status_code=400, detail="Cannot delete policy: It is being used by one or more queue pairs")

        # Delete a specific policy
        query = {"active_learning_policy_id": active_learning_policy_id}
        policy = request.app.active_learning_policies_collection.find_one(query)

        if not policy:
            # If the policy does not exist, return a 404 error
            raise HTTPException(status_code=404, detail="Policy not found")

        # Delete the specific policy
        request.app.active_learning_policies_collection.delete_one(query)
        return {"status": "success", "message": f"Policy with ID {active_learning_policy_id} deleted successfully."}
    else:
        # If no ID is provided, check if there are any policies used by queue pairs
        if request.app.active_learning_queue_pairs_collection.find_one({"active_learning_policy_id": {"$exists": True}}):
            raise HTTPException(status_code=400, detail="Cannot delete all policies: One or more are being used by queue pairs")

        # Delete all policies
        request.app.active_learning_policies_collection.delete_many({})
        return {"status": "success", "message": "All policies deleted successfully."}


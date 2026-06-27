import pytest
import os
from app.services.policy_loader import load_policy

@pytest.fixture
def policy_config():
    policy_path = os.path.join(os.path.dirname(__file__), "../policy_terms.json")
    return load_policy(policy_path)

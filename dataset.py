import os

from datasets import load_dataset
from huggingface_hub import login

# Authenticate with your token
login(token=os.environ["HF_TOKEN"])

# Load the dataset
ds = load_dataset("hackaprompt/hackaprompt-dataset")

# Save locally to disk
ds.save_to_disk("hackaprompt_local")

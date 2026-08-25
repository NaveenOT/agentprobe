"""Import a bounded HackAPrompt sample into MongoDB and ChromaDB.

Install optional dependencies first: pip install -e ".[datasets]"
"""

import argparse
import hashlib
import os

import chromadb
from datasets import load_dataset
from pymongo import MongoClient


def prompt_from_row(row: dict) -> str | None:
    for key in ("user_input", "prompt", "text", "attack"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=2_000)
    parser.add_argument("--mongodb-uri", default=os.getenv("AGENTPROBE_MONGODB_URI", "mongodb://localhost:27017"))
    parser.add_argument("--chroma-path", default="data/chroma")
    args = parser.parse_args()

    dataset = load_dataset("hackaprompt/hackaprompt-dataset", split="train", streaming=True)
    mongo = MongoClient(args.mongodb_uri).agentprobe.attack_templates
    chroma = chromadb.PersistentClient(path=args.chroma_path)
    vectors = chroma.get_or_create_collection("attack_templates")

    imported = 0
    for row in dataset:
        prompt = prompt_from_row(row)
        if not prompt:
            continue
        template_id = f"hackaprompt-{hashlib.sha256(prompt.encode()).hexdigest()[:16]}"
        document = {
            "id": template_id,
            "category": "unclassified",
            "technique": "community_submission",
            "prompt": prompt,
            "source": "HackAPrompt",
            "prerequisites": [],
        }
        mongo.update_one({"id": template_id}, {"$set": document}, upsert=True)
        vectors.upsert(ids=[template_id], documents=[prompt], metadatas=[{"source": "HackAPrompt"}])
        imported += 1
        if imported >= args.limit:
            break

    print(f"Imported {imported} attack templates")


if __name__ == "__main__":
    main()

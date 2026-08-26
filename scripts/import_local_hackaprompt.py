"""Normalize the local HackAPrompt Arrow dataset into MongoDB attack templates."""

import argparse
import hashlib

from agentprobe.templates import BUILTIN_TEMPLATES, classify_attack
from datasets import DatasetDict, load_from_disk
from pymongo import MongoClient, UpdateOne
from tqdm import tqdm


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-path", default="hackaprompt_local")
    parser.add_argument("--mongodb-uri", default="mongodb://localhost:27017")
    parser.add_argument("--database", default="agentprobe")
    parser.add_argument("--batch-size", type=int, default=1_000)
    args = parser.parse_args()

    loaded = load_from_disk(args.dataset_path)
    dataset = loaded["train"] if isinstance(loaded, DatasetDict) else loaded
    successful_indices = [index for index, correct in enumerate(dataset["correct"]) if correct]
    successful = dataset.select(successful_indices)

    client = MongoClient(args.mongodb_uri, serverSelectionTimeoutMS=5_000)
    collection = client[args.database].attack_templates
    collection.create_index("id", unique=True)
    collection.create_index("tags")
    collection.create_index([("category", 1), ("source", 1)])

    operations: list[UpdateOne] = []
    imported_ids: set[str] = set()
    for template in BUILTIN_TEMPLATES:
        document = template.model_dump(mode="json")
        operations.append(UpdateOne({"id": template.id}, {"$set": document}, upsert=True))

    imported = 0
    for row in tqdm(successful, desc="Importing successful attacks"):
        prompt = str(row.get("user_input") or "").strip()
        if len(prompt) < 8 or len(prompt) > 8_000:
            continue
        digest = hashlib.sha256(prompt.encode()).hexdigest()[:16]
        template_id = f"hackaprompt-{digest}"
        if template_id in imported_ids:
            continue
        imported_ids.add(template_id)
        category = classify_attack(prompt)
        document = {
            "id": template_id,
            "category": category.value,
            "technique": f"HackAPrompt level {row.get('level', 'unknown')}",
            "prompt": prompt,
            "source": "HackAPrompt",
            "prerequisites": [],
            "tags": [category.value],
            "metadata": {
                "level": row.get("level"),
                "score": row.get("score"),
                "original_model": row.get("model"),
                "expected_completion": row.get("expected_completion"),
            },
        }
        operations.append(UpdateOne({"id": template_id}, {"$set": document}, upsert=True))
        imported += 1
        if len(operations) >= args.batch_size:
            collection.bulk_write(operations, ordered=False)
            operations.clear()

    if operations:
        collection.bulk_write(operations, ordered=False)
    print(f"Imported {imported:,} unique successful attacks into {args.database}.attack_templates")
    client.close()


if __name__ == "__main__":
    main()

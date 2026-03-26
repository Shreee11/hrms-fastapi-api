from bson import ObjectId


def serialize_doc(doc: dict) -> dict:
    """Convert a MongoDB document's _id ObjectId to a string 'id' field."""
    if doc is None:
        return None
    doc = dict(doc)
    if "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    if "employee_id" in doc and isinstance(doc["employee_id"], ObjectId):
        doc["employee_id"] = str(doc["employee_id"])
    return doc

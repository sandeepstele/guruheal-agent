from pydantic import BaseModel
from typing import Optional, List

class QueryRequest(BaseModel):
    query: str
    doc_ids: Optional[List[str]] = ["vamsi_test"]
    group_id: Optional[str] = None

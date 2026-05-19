from pydantic import BaseModel


class ExecutionRunRead(BaseModel):
    id: str
    project_id: str
    run_type: str
    status: str
    input_json: dict | None = None
    output_json: dict | None = None

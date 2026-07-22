from pydantic import BaseModel


class ExecutionRunRead(BaseModel):
    id: str
    project_id: str
    run_type: str
    status: str
    parent_execution_run_id: str | None = None
    attempt_number: int = 1
    runtime_run_id: str | None = None
    input_json: dict | None = None
    output_json: dict | None = None

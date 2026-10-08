"""接口请求模型（Pydantic v2）。"""
from typing import Any, List, Optional, Union

from pydantic import BaseModel, Field


class RiskCheckRequest(BaseModel):
    """POST /api/risk/check 请求体。"""
    event_type: str = Field(..., description="业务事件类型")
    source_id: str = Field(..., description="来源标识")
    user_id: Optional[str] = Field(None, description="用户编号")
    order_id: Optional[str] = Field(None, description="订单编号")
    event_payload: Optional[dict] = Field(None, description="业务事件附加载荷（可选）")


class RuleCondition(BaseModel):
    """规则条件叶子节点：{"op": "gte", "feature": "order_amount", "value": 5000}"""
    op: str
    feature: str
    value: Any = None


class RuleUpsertRequest(BaseModel):
    """新增规则。"""
    rule_code: str
    rule_name: str
    rule_status: str = "enabled"
    priority: int = 100
    score: int = 10
    condition_json: Union[dict, str]
    description: Optional[str] = ""


class RuleUpdateRequest(RuleUpsertRequest):
    """更新规则（在新增字段基础上追加 id）。"""
    id: int


class RuleStatusRequest(BaseModel):
    id: int
    rule_status: str


class RuleDeleteRequest(BaseModel):
    id: int


class CaseReviewRequest(BaseModel):
    """POST /api/risk/cases/review 请求体。"""
    case_id: int
    review_result: str = Field(..., description="approve / reject / resolve")
    review_remark: Optional[str] = ""
    reviewer_id: Optional[str] = Field(None, description="审核人（缺省时前端传当前角色）")


class BlacklistCreateRequest(BaseModel):
    blacklist_type: str
    blacklist_value: str
    remark: Optional[str] = ""
    status: str = "active"


class BlacklistDeleteRequest(BaseModel):
    id: int


class BlacklistBatchRequest(BaseModel):
    """批量导入：每行 type,value,remark。"""
    items: List[BlacklistCreateRequest]

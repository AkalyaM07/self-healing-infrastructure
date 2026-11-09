from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class AlertItem(BaseModel):
    status: str
    labels: Dict[str, str] = Field(default_factory=dict)
    annotations: Dict[str, str] = Field(default_factory=dict)
    startsAt: Optional[str] = None
    endsAt: Optional[str] = None
    generatorURL: Optional[str] = None
    fingerprint: Optional[str] = None

class AlertmanagerPayload(BaseModel):
    version: Optional[str] = "4"
    groupKey: Optional[str] = None
    status: str
    receiver: Optional[str] = None
    groupLabels: Dict[str, str] = Field(default_factory=dict)
    commonLabels: Dict[str, str] = Field(default_factory=dict)
    commonAnnotations: Dict[str, str] = Field(default_factory=dict)
    externalURL: Optional[str] = None
    alerts: List[AlertItem] = Field(default_factory=list)

class ServerStatus(BaseModel):
    infrastructure_status: str
    server_status: str
    nginx_status: str
    nginx_http_code: Optional[int]
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    website_available: bool
    last_health_check: str
    last_failure_time: Optional[str]
    total_alerts: int
    successful_recoveries: int
    failed_recoveries: int

class MetricsData(BaseModel):
    timestamps: List[str]
    cpu_history: List[float]
    memory_history: List[float]
    disk_usage: float
    network_rx_mb: float
    network_tx_mb: float

class RecoveryHistoryItem(BaseModel):
    id: int
    event_id: str
    service_name: str
    failure_reason: str
    detection_time: str
    recovery_action: str
    recovery_start_time: Optional[str]
    recovery_result: str
    recovery_completion_time: Optional[str]
    execution_output: Optional[str]

class ActivityItem(BaseModel):
    id: int
    timestamp: str
    event_type: str
    title: str
    description: str
    badge_color: str

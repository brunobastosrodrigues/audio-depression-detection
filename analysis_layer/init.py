from fastapi import FastAPI

# Inbound adapters (routers)
from adapters.inbound.RestAnalyzeMetricsAdapter import create_service_analyze_metrics
from adapters.inbound.RestDeriveIndicatorScoresAdapter import (
    create_service_derive_indicator_scores,
)
from adapters.inbound.RestFinetuneBaselineAdapter import (
    create_service_finetune_baseline,
)
from adapters.inbound.RestListUsersAdapter import router as users_router
from adapters.inbound.RestBoardsAdapter import create_service_boards
from adapters.inbound.RestEnvironmentsAdapter import create_service_environments

# Outbound adapters
from adapters.outbound.MongoPersistenceAdapter import MongoPersistenceAdapter

# Core
from core.use_cases.AnalyzeMetricsUseCase import AnalyzeMetricsUseCase
from core.use_cases.DeriveIndicatorScoresUseCase import DeriveIndicatorScoresUseCase
from core.baseline.BaselineManager import BaselineManager


# ---------------------------------------------------------
# Create FastAPI application
# ---------------------------------------------------------

app = FastAPI()

# ---------------------------------------------------------
# Instantiate core components
# ---------------------------------------------------------

baseline_manager = BaselineManager()
repository = MongoPersistenceAdapter()

analyze_metrics_use_case = AnalyzeMetricsUseCase(repository)
derive_indicator_scores_use_case = DeriveIndicatorScoresUseCase(repository)

# ---------------------------------------------------------
# Create routers from adapters
# ---------------------------------------------------------

app_analyze_metrics = create_service_analyze_metrics(
    analyze_metrics_use_case, baseline_manager
)
app_derive_indicator_scores = create_service_derive_indicator_scores(
    derive_indicator_scores_use_case
)
app_finetune_baseline = create_service_finetune_baseline(baseline_manager)
app_boards = create_service_boards(repository)
app_environments = create_service_environments(repository)

# ---------------------------------------------------------
# Register routers with FastAPI
# ---------------------------------------------------------

app.include_router(app_analyze_metrics)
app.include_router(app_derive_indicator_scores)
app.include_router(app_finetune_baseline)
app.include_router(users_router)
app.include_router(app_boards)
app.include_router(app_environments)

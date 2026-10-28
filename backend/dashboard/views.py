from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import F, Q
from django.shortcuts import get_object_or_404, render

from infrastructure.models import Status

from . import queries

PAGE_SIZE = 25


@login_required
def summary(request):
    return render(request, "dashboard/summary.html", {"active": "summary", **queries.summary_data()})


@login_required
def resource_list(request):
    status = request.GET.get("status", "")
    search = request.GET.get("q", "").strip()
    sort = request.GET.get("sort", "risk")

    disks = queries.disks_with_latest()
    if status in Status.values:
        disks = disks.filter(status=status)
    else:
        status = ""
    if search:
        disks = disks.filter(Q(identifier__icontains=search) | Q(name__icontains=search))
    if sort == "name":
        disks = disks.order_by("identifier")
    else:
        sort = "risk"
        disks = disks.order_by(F("risk_score").desc(nulls_last=True), "identifier")

    page = Paginator(disks, PAGE_SIZE).get_page(request.GET.get("page"))
    params = {k: v for k, v in {"status": status, "q": search, "sort": sort}.items() if v}
    return render(request, "dashboard/resource_list.html", {
        "active": "resources", "page_obj": page, "status": status, "q": search, "sort": sort,
        "statuses": Status.choices, "qs": urlencode(params),
    })


@login_required
def resource_detail(request, pk):
    resource = get_object_or_404(queries.disks_with_latest(), pk=pk)
    history = resource.predictions.select_related("model_version").order_by("-window_end", "-created_at")[:20]
    return render(request, "dashboard/resource_detail.html", {
        "active": "resources", "resource": resource, "history": history,
        "chart": queries.chart_data(resource),
    })


@login_required
def models_page(request):
    return render(request, "dashboard/models.html", {"active": "models", "cards": queries.model_cards()})

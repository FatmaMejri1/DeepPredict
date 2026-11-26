from django.contrib.admin.apps import AdminConfig


class DeepPredictAdminConfig(AdminConfig):
    """Use the existing default Admin site with DeepPredict role gating."""

    default_site = "accounts.admin_site.SysAdminAdminSite"

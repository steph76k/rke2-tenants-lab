#!/usr/bin/env python3
"""Retired per-tenant entrypoint: never write the historical states again."""
raise SystemExit("Per-tenant states are retired. Use scripts/terraform-admin.py <command> for the shared administrative state; see docs/remote-state.md.")

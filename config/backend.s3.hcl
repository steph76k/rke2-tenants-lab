bucket                      = "afi-terraform-state"
region                      = "us-east-1"
endpoints                   = { s3 = "https://192.168.1.197:9000" }
use_path_style              = true
use_lockfile                = true
encrypt                     = true
skip_credentials_validation = true
skip_region_validation      = true
skip_requesting_account_id   = true
skip_metadata_api_check     = true
skip_s3_checksum            = true
# Key is supplied by scripts/terraform-tenant.py; credentials and SSE-C key use env.

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = PROJECT_ROOT / "react-ui" / "Dockerfile"
NGINX_TEMPLATE = PROJECT_ROOT / "react-ui" / "nginx.conf.template"
STAGING_ENV_EXAMPLE = PROJECT_ROOT / "deploy" / "staging.env.example"


def test_nginx_uses_the_container_dns_resolver_dynamically():
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    template = NGINX_TEMPLATE.read_text(encoding="utf-8")

    assert "NGINX_ENTRYPOINT_LOCAL_RESOLVERS=1" in dockerfile
    assert "resolver ${NGINX_LOCAL_RESOLVERS} valid=10s;" in template
    assert "set $api_upstream ${API_UPSTREAM};" in template
    assert "proxy_pass http://$api_upstream;" in template
    assert "proxy_pass http://${API_UPSTREAM}/;" not in template


def test_nginx_preserves_runtime_variables_and_api_path_rewriting():
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    template = NGINX_TEMPLATE.read_text(encoding="utf-8")

    assert (
        "NGINX_ENVSUBST_FILTER=^(API_UPSTREAM|NGINX_LOCAL_RESOLVERS)$"
        in dockerfile
    )
    assert "rewrite ^/api/(.*)$ /$1 break;" in template
    assert "proxy_set_header Host $host;" in template
    assert "proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;" in template
    assert "proxy_set_header X-Forwarded-Proto $scheme;" in template


def test_staging_contract_exposes_the_nginx_listener_port():
    staging_contract = STAGING_ENV_EXAMPLE.read_text(encoding="utf-8")

    assert "PORT=80" in staging_contract.splitlines()


def test_every_web_response_has_safe_browser_boundary_headers():
    template = NGINX_TEMPLATE.read_text(encoding="utf-8")

    assert template.count('add_header X-Frame-Options "DENY" always;') == 3
    assert template.count(
        'add_header Content-Security-Policy "frame-ancestors \'none\'" always;'
    ) == 3
    assert template.count(
        'add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;'
    ) == 3

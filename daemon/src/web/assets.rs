//! Static asset serving for Squirrel web UI.

use axum::{
    body::Body,
    http::{header, Request, StatusCode},
    response::{IntoResponse, Response},
};
use rust_embed::Embed;

#[derive(Embed)]
#[folder = "src/web/static"]
struct Asset;

/// Serve static files or fall back to index.html for SPA routing.
pub async fn serve_static(req: Request<Body>) -> impl IntoResponse {
    let path = req.uri().path().trim_start_matches('/');

    // Try exact path first
    if let Some(content) = Asset::get(path) {
        return response_for_asset(path, &content.data);
    }

    // Fall back to index.html for SPA routing
    if let Some(content) = Asset::get("index.html") {
        return response_for_asset("index.html", &content.data);
    }

    (StatusCode::NOT_FOUND, "Not found").into_response()
}

fn response_for_asset(path: &str, data: &[u8]) -> Response {
    let mime = mime_guess::from_path(path)
        .first_or_octet_stream()
        .to_string();

    Response::builder()
        .status(StatusCode::OK)
        .header(header::CONTENT_TYPE, mime)
        .body(Body::from(data.to_vec()))
        .unwrap()
}

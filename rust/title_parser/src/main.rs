//! Fast title-line parser for bulk imports.

use regex::Regex;
use serde::Serialize;
use std::io::{self, Read};

#[derive(Debug, Serialize)]
struct ExtractedTitle {
    title: String,
    year: Option<u16>,
    imdb_id: Option<String>,
    raw: String,
}

fn parse_line(line: &str) -> Option<ExtractedTitle> {
    let line = line.trim();
    if line.is_empty() || line.starts_with('#') {
        return None;
    }

    let imdb_re = Regex::new(r"tt\d{7,8}").unwrap();
    let year_paren = Regex::new(r"\((\d{4})\)").unwrap();
    let numbered = Regex::new(r"^\s*\d+[\.\)]\s*(.+?)(?:\s*\((\d{4})\))?\s*$").unwrap();
    let bullet = Regex::new(r"^\s*[-*•]\s+(.+?)(?:\s*\((\d{4})\))?\s*$").unwrap();

    if let Some(m) = imdb_re.find(line) {
        let imdb_id = m.as_str().to_string();
        let mut title_part = imdb_re.replace(line, "").trim().trim_matches(|c| c == '-' || c == '–' || c == '|').to_string();
        let year = year_paren
            .captures(line)
            .and_then(|c| c.get(1))
            .and_then(|y| y.as_str().parse().ok());
        if title_part.is_empty() {
            title_part = imdb_id.clone();
        }
        return Some(ExtractedTitle {
            title: title_part,
            year,
            imdb_id: Some(imdb_id),
            raw: line.to_string(),
        });
    }

    for re in [&numbered, &bullet] {
        if let Some(caps) = re.captures(line) {
            let mut title = caps.get(1)?.as_str().trim().to_string();
            let year = caps
                .get(2)
                .and_then(|y| y.as_str().parse().ok())
                .or_else(|| {
                    year_paren
                        .captures(&title)
                        .and_then(|c| c.get(1))
                        .and_then(|y| y.as_str().parse().ok())
                });
            if year.is_some() {
                title = year_paren.replace_all(&title, "").trim().to_string();
            }
            return Some(ExtractedTitle {
                title,
                year,
                imdb_id: None,
                raw: line.to_string(),
            });
        }
    }

    if line.len() > 1 {
        let year = year_paren
            .captures(line)
            .and_then(|c| c.get(1))
            .and_then(|y| y.as_str().parse().ok());
        let title = if year.is_some() {
            year_paren.replace_all(line, "").trim().to_string()
        } else {
            line.to_string()
        };
        return Some(ExtractedTitle {
            title,
            year,
            imdb_id: None,
            raw: line.to_string(),
        });
    }
    None
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let input = if args.iter().any(|a| a == "--stdin") {
        let mut buf = String::new();
        io::stdin().read_to_string(&mut buf).expect("read stdin");
        buf
    } else if args.len() > 1 {
        args[1].clone()
    } else {
        String::new()
    };

    let results: Vec<ExtractedTitle> = input
        .lines()
        .filter_map(parse_line)
        .collect();

    println!("{}", serde_json::to_string(&results).unwrap());
}

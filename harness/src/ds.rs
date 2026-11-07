//! usage: ds <root> <list.txt>... — parse every file of each group (first path component) per round;
//! prints "<group>\t<files>\t<bytes>\t<median ns per round>\t<errors>"
use std::hint::black_box;
use std::time::Instant;
fn main() {
    let a: Vec<String> = std::env::args().collect();
    let root = &a[1];
    let mut groups: Vec<(String, Vec<String>)> = Vec::new();
    for list in &a[2..] {
        for rel in std::fs::read_to_string(list).unwrap().lines() {
            let rel = rel.trim();
            if rel.is_empty() { continue; }
            let Ok(t) = std::fs::read_to_string(format!("{root}/{rel}")) else { continue };
            let g = rel.split(|c: char| c == '/' || c == '\\').next().unwrap().to_string();
            let t = t.trim_start_matches('\u{feff}').to_string();
            match groups.iter_mut().find(|(n, _)| *n == g) { Some((_, v)) => v.push(t), None => groups.push((g, vec![t])) }
        }
    }
    for (g, texts) in &groups {
        let parse = |t: &str| roxmltree::Document::parse_with_options(t, roxmltree::ParsingOptions { allow_dtd: true, ..Default::default() }).is_err();
        let errs = texts.iter().filter(|t| parse(t)).count();
        let bytes: usize = texts.iter().map(|t| t.len()).sum();
        let mut iters = 1u32;
        loop {
            let t0 = Instant::now();
            for _ in 0..iters { for t in texts { black_box(parse(black_box(t))); } }
            if t0.elapsed().as_millis() >= 100 { break; }
            iters *= 2;
        }
        let mut s: Vec<f64> = (0..9).map(|_| {
            let t0 = Instant::now();
            for _ in 0..iters { for t in texts { black_box(parse(black_box(t))); } }
            t0.elapsed().as_nanos() as f64 / iters as f64
        }).collect();
        s.sort_by(|a, b| a.partial_cmp(b).unwrap());
        println!("{g}\t{}\t{bytes}\t{:.0}\t{errs}", texts.len(), s[4]);
    }
}

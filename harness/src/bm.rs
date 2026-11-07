//! usage: bm <files...>  — prints "<file>\t<median ns per parse>\t<peak bytes>\t<final bytes>"
use std::alloc::{GlobalAlloc, Layout, System};
use std::hint::black_box;
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering::Relaxed};
use std::time::Instant;

struct Counting;
static ON: AtomicBool = AtomicBool::new(false);
static CUR: AtomicUsize = AtomicUsize::new(0);
static PEAK: AtomicUsize = AtomicUsize::new(0);
unsafe impl GlobalAlloc for Counting {
    unsafe fn alloc(&self, l: Layout) -> *mut u8 {
        if ON.load(Relaxed) { let c = CUR.fetch_add(l.size(), Relaxed) + l.size(); PEAK.fetch_max(c, Relaxed); }
        System.alloc(l)
    }
    unsafe fn dealloc(&self, p: *mut u8, l: Layout) {
        if ON.load(Relaxed) { CUR.fetch_sub(l.size(), Relaxed); }
        System.dealloc(p, l)
    }
    unsafe fn realloc(&self, p: *mut u8, l: Layout, n: usize) -> *mut u8 {
        if ON.load(Relaxed) {
            if n > l.size() { let c = CUR.fetch_add(n - l.size(), Relaxed) + n - l.size(); PEAK.fetch_max(c, Relaxed); }
            else { CUR.fetch_sub(l.size() - n, Relaxed); }
        }
        System.realloc(p, l, n)
    }
}
#[global_allocator]
static A: Counting = Counting;

fn opts<'a>() -> roxmltree::ParsingOptions<'a> {
    roxmltree::ParsingOptions { allow_dtd: true, ..Default::default() }
}

fn main() {
    for path in std::env::args().skip(1) {
        let text = std::fs::read_to_string(&path).unwrap();
        let text = text.trim_start_matches('\u{feff}');
        // memory: one counted parse
        CUR.store(0, Relaxed); PEAK.store(0, Relaxed); ON.store(true, Relaxed);
        let doc = roxmltree::Document::parse_with_options(text, opts()).unwrap();
        let fin = CUR.load(Relaxed);
        drop(doc);
        ON.store(false, Relaxed);
        let peak = PEAK.load(Relaxed);
        // time: samples of >= 40 ms each
        let mut iters = 1u32;
        loop {
            let t = Instant::now();
            for _ in 0..iters { black_box(roxmltree::Document::parse_with_options(black_box(text), opts()).unwrap()); }
            if t.elapsed().as_millis() >= 40 { break; }
            iters *= 2;
        }
        let mut samples: Vec<f64> = (0..7).map(|_| {
            let t = Instant::now();
            for _ in 0..iters { black_box(roxmltree::Document::parse_with_options(black_box(text), opts()).unwrap()); }
            t.elapsed().as_nanos() as f64 / iters as f64
        }).collect();
        samples.sort_by(|a, b| a.partial_cmp(b).unwrap());
        let name = std::path::Path::new(&path).file_name().unwrap().to_string_lossy();
        println!("{name}\t{:.0}\t{peak}\t{fin}", samples[3]);
    }
}

import { useEffect, useMemo, useRef, useState } from 'react';
import './App.css';

const initialForm = {
  university: 'Simon Fraser University',
  query: 'Easy online class with no finals',
  department_preference: 'All Departments'
};

const featureCards = [
  {
    title: 'Fast Filters',
    description: 'Search by dept, GPA, and delivery mode. Find what you need in seconds.'
  },
  {
    title: 'Real Ratings',
    description: 'Aggregated from thousands of student feedback. Trust the community.'
  },
  {
    title: 'Schedule-Friendly',
    description: 'Find classes that fit your week. No more scheduling conflicts.'
  },
  {
    title: 'Plan Ahead',
    description: 'Save courses and compare later. Build your perfect semester.'
  }
];

const clamp = (value, min = 0, max = 1) => Math.min(max, Math.max(min, value));
const easeOut = (t) => 1 - (1 - t) ** 3;
const easeIn = (t) => t ** 2;
const lerp = (a, b, t) => a + (b - a) * t;

function toTransform(x = 0, y = 0, scale = 1) {
  return `translate3d(${x}px, ${y}px, 0) scale(${scale})`;
}

function sceneProgress(wrapper) {
  if (!wrapper) return 0;
  const total = Math.max(1, wrapper.offsetHeight - window.innerHeight);
  const rect = wrapper.getBoundingClientRect();
  const scrolled = clamp(-rect.top, 0, total);
  return scrolled / total;
}

function applyStyle(element, { x = 0, y = 0, scale = 1, opacity = 1 }) {
  if (!element) return;
  element.style.transform = toTransform(x, y, scale);
  element.style.opacity = String(opacity);
}

function App() {
  const [form, setForm] = useState(initialForm);
  const [loading, setLoading] = useState(false);
  const [departmentsLoading, setDepartmentsLoading] = useState(true);
  const [error, setError] = useState('');
  const [results, setResults] = useState([]);
  const [departments, setDepartments] = useState(['All Departments']);
  const [savedCourses, setSavedCourses] = useState(() => {
    try {
      const raw = localStorage.getItem('smg_saved_courses');
      return new Set(raw ? JSON.parse(raw) : []);
    } catch {
      return new Set();
    }
  });
  const [isScrolled, setIsScrolled] = useState(false);
  const [isLoaded, setIsLoaded] = useState(false);
  const [reduceMotion, setReduceMotion] = useState(false);

  const heroWrapRef = useRef(null);
  const heroHeadlineRef = useRef(null);
  const heroPillRef = useRef(null);
  const heroSubRef = useRef(null);
  const heroCtaRef = useRef(null);
  const heroHintRef = useRef(null);

  const searchWrapRef = useRef(null);
  const searchHeadlineRef = useRef(null);
  const searchPillRef = useRef(null);
  const searchCardRef = useRef(null);
  const searchIconLeftRef = useRef(null);
  const searchIconRightRef = useRef(null);

  const resultsWrapRef = useRef(null);
  const resultsHeadlineRef = useRef(null);
  const resultsPillRef = useRef(null);
  const resultsShellRef = useRef(null);
  const resultsIconLeftRef = useRef(null);
  const resultsIconRightRef = useRef(null);
  const resultCardRefs = useRef([]);

  const snapLockRef = useRef(false);

  useEffect(() => {
    resultCardRefs.current = resultCardRefs.current.slice(0, results.length);
  }, [results.length]);

  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReduceMotion(media.matches);
    update();
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => setIsLoaded(true), 80);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    const loadDepartments = async () => {
      try {
        const response = await fetch('/data/departments_1482.txt');
        if (!response.ok) {
          throw new Error(`Unable to load departments (${response.status})`);
        }

        const text = await response.text();
        const list = text
          .split('\n')
          .map((line) => line.trim())
          .filter(Boolean);

        setDepartments(['All Departments', ...list]);
      } catch (err) {
        setError(err.message);
      } finally {
        setDepartmentsLoading(false);
      }
    };

    loadDepartments();
  }, []);

  useEffect(() => {
    localStorage.setItem('smg_saved_courses', JSON.stringify(Array.from(savedCourses)));
  }, [savedCourses]);

  useEffect(() => {
    const onScroll = () => setIsScrolled(window.scrollY > 80);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  useEffect(() => {
    if (reduceMotion) return;

    const updateScenes = () => {
      const vw = window.innerWidth;
      const vh = window.innerHeight;

      const heroP = sceneProgress(heroWrapRef.current);
      const heroExit = clamp((heroP - 0.7) / 0.3);
      applyStyle(heroHeadlineRef.current, {
        x: lerp(0, -0.55 * vw, easeIn(heroExit)),
        opacity: lerp(1, 0.04, easeIn(heroExit))
      });
      applyStyle(heroPillRef.current, {
        y: lerp(0, -0.35 * vh, easeIn(heroExit)),
        opacity: lerp(1, 0.35, easeIn(heroExit))
      });
      applyStyle(heroSubRef.current, {
        x: lerp(0, -0.3 * vw, easeIn(clamp((heroP - 0.74) / 0.26))),
        opacity: lerp(1, 0.25, easeIn(clamp((heroP - 0.74) / 0.26)))
      });
      applyStyle(heroCtaRef.current, {
        y: lerp(0, 0.25 * vh, easeIn(clamp((heroP - 0.72) / 0.28))),
        opacity: lerp(1, 0.15, easeIn(clamp((heroP - 0.72) / 0.28)))
      });
      applyStyle(heroHintRef.current, {
        opacity: lerp(0.7, 0, easeIn(clamp((heroP - 0.75) / 0.25)))
      });

      const searchP = sceneProgress(searchWrapRef.current);
      const searchIn = easeOut(clamp(searchP / 0.3));
      const searchOut = easeIn(clamp((searchP - 0.7) / 0.3));
      applyStyle(searchCardRef.current, {
        x: lerp(0, 0.55 * vw, searchOut),
        y: lerp(0.9 * vh, 0, searchIn),
        scale: lerp(0.92, 1, searchIn),
        opacity: lerp(0, 1, searchIn) * lerp(1, 0.1, searchOut)
      });
      applyStyle(searchHeadlineRef.current, {
        x: lerp(-0.6 * vw, 0, clamp((searchP - 0.06) / 0.24)) + lerp(0, -0.35 * vw, searchOut),
        opacity: lerp(0, 1, clamp((searchP - 0.06) / 0.24)) * lerp(1, 0.25, searchOut)
      });
      applyStyle(searchPillRef.current, {
        y: lerp(-0.4 * vh, 0, clamp((searchP - 0.1) / 0.2)),
        opacity: lerp(0, 1, clamp((searchP - 0.1) / 0.2)) * lerp(1, 0.3, searchOut)
      });
      applyStyle(searchIconLeftRef.current, {
        y: lerp(0.4 * vh, 0, clamp((searchP - 0.14) / 0.16)) + lerp(0, 0.3 * vh, searchOut),
        opacity: lerp(0, 1, clamp((searchP - 0.14) / 0.16)) * lerp(1, 0.2, searchOut)
      });
      applyStyle(searchIconRightRef.current, {
        y: lerp(0.4 * vh, 0, clamp((searchP - 0.18) / 0.12)) + lerp(0, 0.3 * vh, searchOut),
        opacity: lerp(0, 1, clamp((searchP - 0.18) / 0.12)) * lerp(1, 0.2, searchOut)
      });

      const resultsP = sceneProgress(resultsWrapRef.current);
      const resultsIn = easeOut(clamp(resultsP / 0.3));
      const resultsOut = easeIn(clamp((resultsP - 0.7) / 0.3));
      applyStyle(resultsShellRef.current, {
        y: lerp(vh, 0, resultsIn) + lerp(0, -0.6 * vh, resultsOut),
        scale: lerp(0.9, 1, resultsIn),
        opacity: lerp(0, 1, resultsIn) * lerp(1, 0.15, resultsOut)
      });
      applyStyle(resultsHeadlineRef.current, {
        x: lerp(-0.6 * vw, 0, clamp((resultsP - 0.08) / 0.22)) + lerp(0, 0.35 * vw, resultsOut),
        opacity: lerp(0, 1, clamp((resultsP - 0.08) / 0.22)) * lerp(1, 0.3, resultsOut)
      });
      applyStyle(resultsPillRef.current, {
        y: lerp(-0.45 * vh, 0, clamp((resultsP - 0.1) / 0.2)),
        opacity: lerp(0, 1, clamp((resultsP - 0.1) / 0.2)) * lerp(1, 0.3, resultsOut)
      });
      applyStyle(resultsIconLeftRef.current, {
        y: lerp(0.45 * vh, 0, clamp((resultsP - 0.14) / 0.16)) + lerp(0, 0.35 * vh, resultsOut),
        opacity: lerp(0, 1, clamp((resultsP - 0.14) / 0.16)) * lerp(1, 0.25, resultsOut)
      });
      applyStyle(resultsIconRightRef.current, {
        y: lerp(0.45 * vh, 0, clamp((resultsP - 0.18) / 0.12)) + lerp(0, 0.35 * vh, resultsOut),
        opacity: lerp(0, 1, clamp((resultsP - 0.18) / 0.12)) * lerp(1, 0.25, resultsOut)
      });

      const cardEntrance = clamp((resultsP - 0.16) / 0.2);
      resultCardRefs.current.forEach((card, index) => {
        const delay = index * 0.08;
        const local = easeOut(clamp((cardEntrance - delay) / (1 - delay)));
        applyStyle(card, {
          y: lerp(40, 0, local),
          opacity: local * lerp(1, 0.6, resultsOut)
        });
      });
    };

    let frame = 0;
    const requestUpdate = () => {
      if (frame) return;
      frame = window.requestAnimationFrame(() => {
        frame = 0;
        updateScenes();
      });
    };

    window.addEventListener('scroll', requestUpdate, { passive: true });
    window.addEventListener('resize', requestUpdate);
    requestUpdate();

    return () => {
      window.removeEventListener('scroll', requestUpdate);
      window.removeEventListener('resize', requestUpdate);
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, [reduceMotion, results.length]);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-visible');
          }
        });
      },
      { threshold: 0.2 }
    );

    document.querySelectorAll('.reveal-on-scroll').forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (reduceMotion) return;

    const points = () => {
      const ids = ['hero-scene', 'search-scene', 'results-scene', 'features', 'footer'];
      return ids
        .map((id) => document.getElementById(id))
        .filter(Boolean)
        .map((el) => {
          const isPinned = el.classList.contains('scene-wrap');
          if (!isPinned) return el.offsetTop;
          return el.offsetTop + Math.max(0, (el.offsetHeight - window.innerHeight) * 0.5);
        });
    };

    let timer = 0;
    const onScroll = () => {
      if (snapLockRef.current) return;
      window.clearTimeout(timer);
      timer = window.setTimeout(() => {
        const anchors = points();
        if (!anchors.length) return;
        const current = window.scrollY;
        let nearest = anchors[0];
        let best = Math.abs(current - nearest);

        for (let i = 1; i < anchors.length; i += 1) {
          const dist = Math.abs(current - anchors[i]);
          if (dist < best) {
            best = dist;
            nearest = anchors[i];
          }
        }

        if (best < window.innerHeight * 0.65) {
          snapLockRef.current = true;
          window.scrollTo({ top: nearest, behavior: 'smooth' });
          window.setTimeout(() => {
            snapLockRef.current = false;
          }, 650);
        }
      }, 120);
    };

    window.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      window.removeEventListener('scroll', onScroll);
      window.clearTimeout(timer);
    };
  }, [reduceMotion]);

  const updateField = (event) => {
    const { name, value } = event.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const scrollTo = (id) => {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const clearFilters = () => {
    setForm(initialForm);
  };

  const toggleSaved = (courseCode) => {
    setSavedCourses((prev) => {
      const next = new Set(prev);
      if (next.has(courseCode)) {
        next.delete(courseCode);
      } else {
        next.add(courseCode);
      }
      return next;
    });
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError('');

    try {
      const response = await fetch('/api/recommendations', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          ...form,
          department_preference:
            form.department_preference === 'All Departments' ? '' : form.department_preference
        })
      });

      if (!response.ok) {
        let detail = '';
        try {
          const payload = await response.json();
          detail = payload.error || payload.stderr || payload.stdout || JSON.stringify(payload);
        } catch {
          // ignore non-json body
        }
        throw new Error(
          detail ? `API returned ${response.status}: ${detail}` : `API returned ${response.status}`
        );
      }

      const payload = await response.json();
      setResults(payload.results ?? []);
      window.setTimeout(() => scrollTo('results-scene'), 150);
    } catch (err) {
      setResults([]);
      setError(`${err.message}. Make sure your Flask API is running at http://localhost:5050.`);
    } finally {
      setLoading(false);
    }
  };

  const resultCount = results.length;

  const avgGpa = useMemo(() => {
    const values = results
      .map((item) => Number(item.avg_gpa))
      .filter((value) => Number.isFinite(value));

    if (!values.length) return 'n/a';
    return (values.reduce((sum, value) => sum + value, 0) / values.length).toFixed(1);
  }, [results]);

  return (
    <main className={`smg ${isLoaded ? 'is-loaded' : ''}`}>
      <nav className={`topbar ${isScrolled ? 'topbar-scrolled' : ''}`}>
        <div className="container topbar-inner">
          <button className="brand" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>
            SaveMyGrade
          </button>
          <div className="nav-links">
            <button onClick={() => scrollTo('features')}>How it works</button>
            <button onClick={() => scrollTo('search-scene')}>Search</button>
            <button onClick={() => scrollTo('results-scene')}>Results</button>
            <button onClick={() => scrollTo('footer')}>FAQ</button>
          </div>
        </div>
      </nav>

      <section className="scene-wrap hero-wrap" id="hero-scene" ref={heroWrapRef}>
        <div className="scene scene-hero">
          <div className="scene-glow" />
          <div className="container hero-content">
            <div className="pill" ref={heroPillRef}>
              A+
            </div>
            <div className="hero-headline" ref={heroHeadlineRef}>
              <h1 className="headline">SaveMyGrade</h1>
              <h2 className="headline">Find easy A&apos;s.</h2>
            </div>
            <p className="subhead" ref={heroSubRef}>
              Paste your query. Pick your dept. Get the easiest professors and GPA-friendly courses in seconds.
            </p>
            <button className="btn-amber" ref={heroCtaRef} onClick={() => scrollTo('search-scene')}>
              Find Easy Classes
            </button>
            <div className="scroll-hint" ref={heroHintRef}>
              Scroll to search
            </div>
          </div>
        </div>
      </section>

      <section className="scene-wrap search-wrap" id="search-scene" ref={searchWrapRef}>
        <div className="scene scene-search" id="search">
          <div className="scene-glow" />
          <div className="container section-content">
            <div className="pill" ref={searchPillRef}>
              A
            </div>
            <h2 className="section-title" ref={searchHeadlineRef}>
              What are you looking for?
            </h2>

            <form className="glass-card search-card" ref={searchCardRef} onSubmit={handleSubmit}>
              <div className="field-grid">
                <label>
                  <span>University</span>
                  <input
                    name="university"
                    value={form.university}
                    onChange={updateField}
                    placeholder="e.g., State University"
                    required
                  />
                </label>

                <label>
                  <span>Department</span>
                  <select
                    name="department_preference"
                    value={form.department_preference}
                    onChange={updateField}
                    disabled={departmentsLoading}
                  >
                    {departments.map((department) => (
                      <option key={department} value={department}>
                        {department}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <label>
                <span>Your Request</span>
                <textarea
                  name="query"
                  value={form.query}
                  onChange={updateField}
                  rows="3"
                  placeholder="e.g., Easy online class with no finals"
                  required
                />
              </label>

              <p className="helper">Example: &quot;Easy online class with no finals&quot;</p>

              <div className="actions">
                <button type="button" className="btn-clear" onClick={clearFilters}>
                  Clear Filters
                </button>
                <button type="submit" className="btn-amber" disabled={loading || departmentsLoading}>
                  {loading ? 'Running...' : 'Get Recommendations'}
                </button>
              </div>
            </form>

            <div className="floating-icon icon-left" ref={searchIconLeftRef} aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none">
                <path d="M9 18h6M10 21h4M8 14a6 6 0 1 1 8 0c-.92.86-1.45 1.66-1.67 2.5h-4.66C9.45 15.66 8.92 14.86 8 14Z" />
              </svg>
            </div>
            <div className="floating-icon icon-right" ref={searchIconRightRef} aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none">
                <path d="m20 20-4-4m1-5a6 6 0 1 1-12 0 6 6 0 0 1 12 0Z" />
              </svg>
            </div>

            {error ? <p className="error-text">{error}</p> : null}
          </div>
        </div>
      </section>

      <section className="scene-wrap results-wrap" id="results-scene" ref={resultsWrapRef}>
        <div className="scene scene-results" id="results">
          <div className="scene-glow" />
          <div className="container section-content">
            <div className="pill" ref={resultsPillRef}>
              B
            </div>
            <div className="results-headline" ref={resultsHeadlineRef}>
              <h2 className="section-title">Here are your easy A&apos;s.</h2>
              <p className="results-sub">Sorted by GPA, difficulty, and real student feedback.</p>
              <p className="results-count">{resultCount} classes found</p>
            </div>

            <div className="glass-card results-shell" ref={resultsShellRef}>
              {loading ? (
                <ul className="results-grid">
                  {[...Array(6)].map((_, index) => (
                    <li className="result-card skeleton-card" key={`skeleton-${index}`}>
                      <div className="skeleton h-28" />
                    </li>
                  ))}
                </ul>
              ) : results.length === 0 ? (
                <div className="empty">No results yet. Run a search above.</div>
              ) : (
                <ul className="results-grid">
                  {results.map((item, index) => {
                    const courseCode = item.course_code ?? `Unknown-${index}`;
                    const saved = savedCourses.has(courseCode);
                    return (
                      <li
                        className="result-card breathe"
                        key={`${courseCode}-${index}`}
                        ref={(el) => {
                          resultCardRefs.current[index] = el;
                        }}
                      >
                        <div className="result-top">
                          <h3>{courseCode}</h3>
                          <button
                            className={`save-btn ${saved ? 'saved' : ''}`}
                            onClick={() => toggleSaved(courseCode)}
                            type="button"
                          >
                            {saved ? 'Saved' : 'Save'}
                          </button>
                        </div>
                        <p className="title">{item.title ?? 'No title available'}</p>
                        <p className="meta">
                          GPA <strong>{item.avg_gpa ?? 'n/a'}</strong> · {item.difficulty ?? 'n/a'}
                        </p>
                        <p className="meta">
                          Prof. <strong>{item.professor ?? 'n/a'}</strong> {item.prof_rating ?? 'n/a'}/5
                        </p>
                        {item.reason ? <p className="quote">&quot;{item.reason}&quot;</p> : null}
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

            <div className="floating-icon icon-left" ref={resultsIconLeftRef} aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none">
                <path d="M4 20V4m4 16v-6m6 6V8m6 12V11" />
              </svg>
            </div>
            <div className="floating-icon icon-right" ref={resultsIconRightRef} aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none">
                <path d="m5 13 4 4L19 7" />
              </svg>
            </div>
          </div>
        </div>
      </section>

      <section className="flow-section features" id="features">
        <div className="container section-content reveal-on-scroll">
          <h2 className="section-title">Built for busy students.</h2>
          <div className="features-grid">
            {featureCards.map((feature, index) => (
              <article
                key={feature.title}
                className="feature-card glass-card reveal-on-scroll"
                style={{ transitionDelay: `${index * 60}ms` }}
              >
                <h3>{feature.title}</h3>
                <p>{feature.description}</p>
              </article>
            ))}
          </div>
          <button className="btn-amber reveal-on-scroll" onClick={() => scrollTo('search-scene')}>
            Start Your Search
          </button>
        </div>
      </section>

      <footer className="flow-section footer" id="footer">
        <div className="container reveal-on-scroll">
          <div className="glass-card footer-card">
            <div className="pill pill-small">A+</div>
            <h3>SaveMyGrade</h3>
            <p>Find easy A&apos;s. Plan smarter.</p>
            <div className="footer-links">
              <button onClick={() => scrollTo('hero-scene')}>How it works</button>
              <button onClick={() => scrollTo('search-scene')}>Search</button>
              <button onClick={() => scrollTo('results-scene')}>Results</button>
              <button onClick={() => scrollTo('features')}>FAQ</button>
            </div>
            <small>© 2026 SaveMyGrade. All rights reserved.</small>
          </div>
        </div>
      </footer>
    </main>
  );
}

export default App;

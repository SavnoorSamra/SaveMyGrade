import { useEffect, useMemo, useRef, useState } from 'react';
import './App.css';

const initialForm = {
  university: 'Simon Fraser University',
  query: 'Easy online class with no finals',
  department_preference: 'All Departments'
};
const ALL_DEPARTMENTS_LABEL = 'All Departments';

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
  const [departmentsError, setDepartmentsError] = useState('');
  const [error, setError] = useState('');
  const [results, setResults] = useState([]);
  const [apiMeta, setApiMeta] = useState(null);
  const [departments, setDepartments] = useState([ALL_DEPARTMENTS_LABEL]);
  const [departmentQuery, setDepartmentQuery] = useState('');
  const [departmentOpen, setDepartmentOpen] = useState(false);
  const [backendStatus, setBackendStatus] = useState({ loading: true, healthy: false, note: '' });
  const [showAllResults, setShowAllResults] = useState(false);
  const [savedCourses, setSavedCourses] = useState(() => {
    try {
      const raw = localStorage.getItem('smg_saved_courses');
      return new Set(raw ? JSON.parse(raw) : []);
    } catch {
      return new Set();
    }
  });
  const [savedCourseMap, setSavedCourseMap] = useState(() => {
    try {
      const raw = localStorage.getItem('smg_saved_course_map');
      const parsed = raw ? JSON.parse(raw) : {};
      return parsed && typeof parsed === 'object' ? parsed : {};
    } catch {
      return {};
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
  const departmentBoxRef = useRef(null);

  const snapLockRef = useRef(false);
  const programmaticScrollRef = useRef(false);

  const selectedDepartment = form.department_preference || ALL_DEPARTMENTS_LABEL;
  const filteredDepartments = useMemo(() => {
    const query = departmentQuery.trim().toLowerCase();
    const source = departments.filter((dept) => dept !== ALL_DEPARTMENTS_LABEL);
    if (!query) {
      return source.slice(0, 120);
    }
    return source.filter((dept) => dept.toLowerCase().includes(query)).slice(0, 120);
  }, [departmentQuery, departments]);

  useEffect(() => {
    resultCardRefs.current = resultCardRefs.current.slice(0, results.length);
  }, [results.length]);

  useEffect(() => {
    setShowAllResults(false);
  }, [results]);

  useEffect(() => {
    if (!results.length || !savedCourses.size) return;
    setSavedCourseMap((prev) => {
      const next = { ...prev };
      let changed = false;
      results.forEach((item, index) => {
        const courseCode = item.course_code ?? `Unknown-${index}`;
        if (!savedCourses.has(courseCode) || next[courseCode]) return;
        next[courseCode] = {
          course_code: courseCode,
          title: item?.title ?? 'No title available',
          department: item?.department ?? '',
          difficulty: item?.difficulty ?? 'n/a',
          professor: item?.professor ?? 'n/a',
          prof_rating: item?.prof_rating ?? 'n/a',
          reason: item?.reason ?? ''
        };
        changed = true;
      });
      return changed ? next : prev;
    });
  }, [results, savedCourses]);

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
    const loadHealth = async () => {
      try {
        const response = await fetch('/api/health');
        if (!response.ok) {
          throw new Error(`health ${response.status}`);
        }
        const payload = await response.json();
        setBackendStatus({
          loading: false,
          healthy: true,
          note: payload.any_gemini_key_configured ? 'AI ranking ready' : 'Heuristic-only mode'
        });
      } catch {
        setBackendStatus({
          loading: false,
          healthy: false,
          note: 'Backend unavailable'
        });
      }
    };

    const loadDepartments = async () => {
      setDepartmentsLoading(true);
      setDepartmentsError('');
      try {
        const response = await fetch('/api/filters');
        if (!response.ok) {
          throw new Error(`filters ${response.status}`);
        }
        const payload = await response.json();
        const list = Array.isArray(payload.departments)
          ? payload.departments.map((d) => String(d || '').trim()).filter(Boolean)
          : [];
        if (!list.length) {
          throw new Error('No departments returned from backend');
        }
        setDepartments([ALL_DEPARTMENTS_LABEL, ...list]);
      } catch {
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
          setDepartments([ALL_DEPARTMENTS_LABEL, ...list]);
          setDepartmentsError('Using local department list (backend filters unavailable).');
        } catch (err) {
          setDepartments([ALL_DEPARTMENTS_LABEL]);
          setDepartmentsError(err.message || 'Failed to load departments');
        }
      } finally {
        setDepartmentsLoading(false);
      }
    };

    loadHealth();
    loadDepartments();
  }, []);

  useEffect(() => {
    const onPointerDown = (event) => {
      if (!departmentBoxRef.current?.contains(event.target)) {
        setDepartmentOpen(false);
      }
    };
    document.addEventListener('pointerdown', onPointerDown);
    return () => document.removeEventListener('pointerdown', onPointerDown);
  }, []);

  useEffect(() => {
    localStorage.setItem('smg_saved_courses', JSON.stringify(Array.from(savedCourses)));
  }, [savedCourses]);

  useEffect(() => {
    localStorage.setItem('smg_saved_course_map', JSON.stringify(savedCourseMap));
  }, [savedCourseMap]);

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
        .map((el) => el.offsetTop);
    };

    let timer = 0;
    const onScroll = () => {
      if (snapLockRef.current || programmaticScrollRef.current) return;
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

        if (best < window.innerHeight * 0.45) {
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
    const target = document.getElementById(id);
    if (!target) return;
    programmaticScrollRef.current = true;
    window.scrollTo({ top: target.offsetTop, behavior: 'smooth' });
    window.setTimeout(() => {
      programmaticScrollRef.current = false;
    }, 700);
  };

  const clearFilters = () => {
    setForm(initialForm);
    setDepartmentQuery('');
    setDepartmentOpen(false);
    setApiMeta(null);
  };

  const toggleSaved = (courseCode, item) => {
    setSavedCourses((prev) => {
      const next = new Set(prev);
      if (next.has(courseCode)) {
        next.delete(courseCode);
      } else {
        next.add(courseCode);
      }
      return next;
    });
    setSavedCourseMap((prev) => {
      const next = { ...prev };
      if (next[courseCode]) {
        delete next[courseCode];
      } else {
        next[courseCode] = {
          course_code: courseCode,
          title: item?.title ?? 'No title available',
          department: item?.department ?? '',
          difficulty: item?.difficulty ?? 'n/a',
          professor: item?.professor ?? 'n/a',
          prof_rating: item?.prof_rating ?? 'n/a',
          reason: item?.reason ?? ''
        };
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
          department:
            form.department_preference === ALL_DEPARTMENTS_LABEL ? '' : form.department_preference,
          department_preference:
            form.department_preference === ALL_DEPARTMENTS_LABEL ? '' : form.department_preference
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
      setApiMeta(payload.meta ?? null);
      window.setTimeout(() => scrollTo('results-scene'), 150);
    } catch (err) {
      setResults([]);
      setApiMeta(null);
      setError(`${err.message}. Make sure your Flask API is running at http://localhost:5050.`);
    } finally {
      setLoading(false);
    }
  };

  const resultCount = results.length;
  const displayedResults = showAllResults ? results : results.slice(0, 5);
  const savedCards = useMemo(
    () => Object.values(savedCourseMap).sort((a, b) => String(a.course_code).localeCompare(String(b.course_code))),
    [savedCourseMap]
  );

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
            <button onClick={() => scrollTo('saved')}>Saved</button>
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
            <div className="status-row">
              <span className={`status-pill ${backendStatus.healthy ? 'ok' : 'warn'}`}>
                {backendStatus.loading
                  ? 'Checking backend...'
                  : backendStatus.healthy
                    ? 'Backend connected'
                    : 'Backend offline'}
              </span>
              <span className="status-note">{backendStatus.note}</span>
            </div>

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

                <label className="department-combobox" ref={departmentBoxRef}>
                  <span>Department</span>
                  <input
                    value={departmentOpen ? departmentQuery : selectedDepartment}
                    onChange={(event) => {
                      setDepartmentQuery(event.target.value);
                      setDepartmentOpen(true);
                    }}
                    onFocus={() => {
                      setDepartmentQuery(selectedDepartment === ALL_DEPARTMENTS_LABEL ? '' : selectedDepartment);
                      setDepartmentOpen(true);
                    }}
                    onKeyDown={(event) => {
                      if (event.key === 'Escape') {
                        setDepartmentOpen(false);
                        setDepartmentQuery('');
                      }
                    }}
                    placeholder="Search department..."
                    disabled={departmentsLoading}
                  />
                  {departmentOpen ? (
                    <div className="department-menu">
                      <button
                        className={`department-option ${selectedDepartment === ALL_DEPARTMENTS_LABEL ? 'active' : ''}`}
                        type="button"
                        onClick={() => {
                          setForm((prev) => ({ ...prev, department_preference: ALL_DEPARTMENTS_LABEL }));
                          setDepartmentQuery('');
                          setDepartmentOpen(false);
                        }}
                      >
                        {ALL_DEPARTMENTS_LABEL}
                      </button>
                      {filteredDepartments.length ? (
                        filteredDepartments.map((department) => (
                          <button
                            className={`department-option ${selectedDepartment === department ? 'active' : ''}`}
                            key={department}
                            type="button"
                            onClick={() => {
                              setForm((prev) => ({ ...prev, department_preference: department }));
                              setDepartmentQuery('');
                              setDepartmentOpen(false);
                            }}
                          >
                            {department}
                          </button>
                        ))
                      ) : (
                        <p className="department-empty">No matching departments.</p>
                      )}
                    </div>
                  ) : null}
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
              {departmentsError ? <p className="helper helper-warning">{departmentsError}</p> : null}

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
            {apiMeta ? (
              <p className="api-meta">
                Model: {apiMeta.model_used || 'n/a'} • Profiles: {apiMeta.class_profiles ?? 0} • Files:{' '}
                {apiMeta.matched_professor_files ?? 0}
              </p>
            ) : null}
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
              <p className="results-sub">Sorted by average difficulty, ratings, and real student feedback.</p>
              <p className="results-count">{resultCount} classes found</p>
            </div>

            <div className="glass-card results-shell" ref={resultsShellRef}>
              {loading ? (
                <ul className="results-grid">
                  {[...Array(5)].map((_, index) => (
                    <li className="result-card skeleton-card" key={`skeleton-${index}`}>
                      <div className="skeleton h-28" />
                    </li>
                  ))}
                </ul>
              ) : results.length === 0 ? (
                <div className="empty">No results yet. Run a search above.</div>
              ) : (
                <>
                  <ul className="results-grid">
                  {displayedResults.map((item, index) => {
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
                            onClick={() => toggleSaved(courseCode, item)}
                            type="button"
                          >
                            {saved ? 'Saved' : 'Save'}
                          </button>
                        </div>
                        <p className="title">{item.title ?? 'No title available'}</p>
                        <p className="meta">
                          Avg Difficulty <strong>{item.difficulty ?? 'n/a'}</strong>
                        </p>
                        <p className="meta">
                          Prof. <strong>{item.professor ?? 'n/a'}</strong> {item.prof_rating ?? 'n/a'}/5
                        </p>
                        {item.reason ? <p className="quote">&quot;{item.reason}&quot;</p> : null}
                      </li>
                    );
                  })}
                </ul>
                {results.length > 5 ? (
                  <div className="results-actions">
                    <button
                      type="button"
                      className="btn-clear"
                      onClick={() => setShowAllResults((prev) => !prev)}
                    >
                      {showAllResults ? 'Show Top 5' : `Show More (${results.length - 5} more)`}
                    </button>
                  </div>
                ) : null}
                </>
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

      <section className="flow-section saved-panel" id="saved">
        <div className="container section-content reveal-on-scroll">
          <div className="saved-header">
            <h2 className="section-title">Saved Courses</h2>
            <p className="saved-count">{savedCards.length} saved</p>
          </div>
          {savedCards.length === 0 ? (
            <div className="glass-card saved-empty">
              <p>No saved courses yet. Tap &quot;Save&quot; on any result card to pin it here.</p>
              <button className="btn-amber" onClick={() => scrollTo('results-scene')}>
                Browse Results
              </button>
            </div>
          ) : (
            <>
              <div className="saved-actions">
                <button
                  type="button"
                  className="btn-clear"
                  onClick={() => {
                    setSavedCourses(new Set());
                    setSavedCourseMap({});
                  }}
                >
                  Clear All Saved
                </button>
              </div>
              <ul className="saved-grid">
                {savedCards.map((item) => (
                  <li className="result-card" key={`saved-${item.course_code}`}>
                    <div className="result-top">
                      <h3>{item.course_code}</h3>
                      <button
                        className="save-btn saved"
                        type="button"
                        onClick={() => toggleSaved(item.course_code, item)}
                      >
                        Remove
                      </button>
                    </div>
                    <p className="title">{item.title}</p>
                    <p className="meta">
                      Avg Difficulty <strong>{item.difficulty}</strong>
                    </p>
                    <p className="meta">
                      Prof. <strong>{item.professor}</strong> {item.prof_rating}/5
                    </p>
                    {item.reason ? <p className="quote">&quot;{item.reason}&quot;</p> : null}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      </section>

      <section className="flow-section features" id="features">
        <div className="container section-content reveal-on-scroll">
          <h2 className="section-title">built for students, by students</h2>
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

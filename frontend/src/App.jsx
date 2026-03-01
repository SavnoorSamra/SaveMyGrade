import { useEffect, useMemo, useRef, useState } from 'react';
import './App.css';

const initialForm = {
  university: 'Simon Fraser University',
  query: 'Easy online class with no finals',
  department_preference: 'All Departments'
};

const faqs = [
  {
    q: 'How are recommendations ranked?',
    a: 'Results are ranked from backend outputs using class GPA trends, difficulty signals, and professor sentiment.'
  },
  {
    q: 'Can I filter by department?',
    a: 'Yes. Department values are sourced from SFU professor data and applied before request submission.'
  },
  {
    q: 'Do saved cards persist?',
    a: 'Yes. Saved cards are stored in local browser storage for quick shortlisting during planning.'
  }
];

function App() {
  const [form, setForm] = useState(initialForm);
  const [loading, setLoading] = useState(false);
  const [departmentsLoading, setDepartmentsLoading] = useState(true);
  const [error, setError] = useState('');
  const [results, setResults] = useState([]);
  const [departments, setDepartments] = useState(['All Departments']);
  const [activeSection, setActiveSection] = useState('search');
  const [openFaq, setOpenFaq] = useState(0);
  const [savedCourses, setSavedCourses] = useState(() => {
    try {
      const raw = localStorage.getItem('smg_saved_courses');
      return new Set(raw ? JSON.parse(raw) : []);
    } catch {
      return new Set();
    }
  });

  const searchRef = useRef(null);
  const howRef = useRef(null);
  const resultsRef = useRef(null);
  const faqRef = useRef(null);

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
    const sections = [
      { key: 'search', ref: searchRef },
      { key: 'how', ref: howRef },
      { key: 'results', ref: resultsRef },
      { key: 'faq', ref: faqRef }
    ];

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];

        if (!visible) {
          return;
        }

        const match = sections.find((section) => section.ref.current === visible.target);
        if (match) {
          setActiveSection(match.key);
        }
      },
      {
        threshold: [0.2, 0.45, 0.7],
        rootMargin: '-20% 0px -35% 0px'
      }
    );

    sections.forEach((section) => {
      if (section.ref.current) {
        observer.observe(section.ref.current);
      }
    });

    return () => observer.disconnect();
  }, []);

  const updateField = (event) => {
    const { name, value } = event.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const clearFilters = () => {
    setForm(initialForm);
  };

  const scrollTo = (ref) => {
    ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const toggleSaved = (code) => {
    setSavedCourses((prev) => {
      const next = new Set(prev);
      if (next.has(code)) {
        next.delete(code);
      } else {
        next.add(code);
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
          // non-json error
        }
        throw new Error(
          detail ? `API returned ${response.status}: ${detail}` : `API returned ${response.status}`
        );
      }

      const payload = await response.json();
      setResults(payload.results ?? []);
      setTimeout(() => scrollTo(resultsRef), 120);
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
      .filter((v) => Number.isFinite(v));
    if (!values.length) return 'n/a';
    return (values.reduce((a, b) => a + b, 0) / values.length).toFixed(1);
  }, [results]);

  const navItems = [
    { key: 'how', label: 'How it works', ref: howRef },
    { key: 'search', label: 'Search', ref: searchRef },
    { key: 'results', label: 'Results', ref: resultsRef },
    { key: 'faq', label: 'FAQ', ref: faqRef }
  ];

  return (
    <main className="smg">
      <nav className="topbar">
        <div className="wrap topbar-inner">
          <button className="brand" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>
            SaveMyGrade
          </button>
          <div className="topnav-links">
            {navItems.map((item) => (
              <button
                key={item.key}
                className={activeSection === item.key ? 'is-active' : ''}
                onClick={() => scrollTo(item.ref)}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
      </nav>

      <section className="section section-blue" ref={searchRef}>
        <div className="floating-icon floating-icon--left" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none">
            <path d="M9 18h6M10 21h4M8 14a6 6 0 1 1 8 0c-.92.86-1.45 1.66-1.67 2.5h-4.66C9.45 15.66 8.92 14.86 8 14Z" />
          </svg>
        </div>
        <div className="floating-icon floating-icon--right" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none">
            <path d="m20 20-4-4m1-5a6 6 0 1 1-12 0 6 6 0 0 1 12 0Z" />
          </svg>
        </div>
        <div className="wrap hero-wrap reveal">
          <div className="grade-pill animate-bob">A</div>
          <h1>What are you looking for?</h1>

          <form className="search-card" onSubmit={handleSubmit}>
            <div className="field-row">
              <label>
                <span>UNIVERSITY</span>
                <input
                  name="university"
                  value={form.university}
                  onChange={updateField}
                  placeholder="e.g., State University"
                  required
                />
              </label>

              <label>
                <span>DEPARTMENT</span>
                <select
                  name="department_preference"
                  value={form.department_preference}
                  onChange={updateField}
                  disabled={departmentsLoading}
                >
                  {departments.map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <label>
              <span>YOUR REQUEST</span>
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
              <button type="button" className="ghost" onClick={clearFilters}>
                Clear Filters
              </button>
              <button type="submit" className="cta" disabled={loading || departmentsLoading}>
                {loading ? 'Running...' : 'Get Recommendations'}
              </button>
            </div>
          </form>

          {error ? <p className="error-text">{error}</p> : null}
        </div>
      </section>

      <section className="section section-purple" ref={howRef}>
        <div className="wrap features-wrap reveal">
          <h2>Built for busy students.</h2>
          <div className="feature-grid">
            <article className="feature-card">
              <h3>Fast Filters</h3>
              <p>Search by dept, GPA, and delivery mode. Find what you need in seconds.</p>
            </article>
            <article className="feature-card">
              <h3>Real Ratings</h3>
              <p>Aggregated from thousands of student feedback signals. Trust the community.</p>
            </article>
            <article className="feature-card">
              <h3>Schedule-Friendly</h3>
              <p>Find classes that fit your week. No more scheduling conflicts.</p>
            </article>
            <article className="feature-card">
              <h3>Plan Ahead</h3>
              <p>Save courses and compare later. Build your perfect semester.</p>
            </article>
          </div>
          <button className="cta" onClick={() => scrollTo(searchRef)}>
            Start Your Search
          </button>
        </div>
      </section>

      <section className="section section-pink" ref={resultsRef}>
        <div className="floating-icon floating-icon--chart" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none">
            <path d="M4 20V4m4 16v-6m6 6V8m6 12V11" />
          </svg>
        </div>
        <div className="floating-icon floating-icon--check" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none">
            <path d="m5 13 4 4L19 7" />
          </svg>
        </div>
        <div className="wrap results-wrap reveal">
          <div className="grade-pill animate-bob">B</div>
          <h2>Here are your easy A&apos;s.</h2>
          <p className="results-sub">Sorted by GPA, difficulty, and real student feedback.</p>
          <p className="results-count">
            {resultCount} classes found • avg GPA {avgGpa}
          </p>

          <div className="results-shell">
            {loading ? (
              <ul className="result-grid">
                {[...Array(3)].map((_, index) => (
                  <li className="result-card skeleton-card" key={`skeleton-${index}`}>
                    <div className="skeleton h-28" />
                  </li>
                ))}
              </ul>
            ) : results.length === 0 ? (
              <div className="empty">No results yet. Run a search above.</div>
            ) : (
              <ul className="result-grid">
                {results.map((item, index) => {
                  const courseCode = item.course_code ?? `Unknown-${index}`;
                  const isSaved = savedCourses.has(courseCode);
                  return (
                    <li className="result-card" key={`${courseCode}-${index}`}>
                      <div className="result-top">
                        <h3>{courseCode}</h3>
                        <button
                          className={`save-btn ${isSaved ? 'saved' : ''}`}
                          onClick={() => toggleSaved(courseCode)}
                          type="button"
                        >
                          {isSaved ? '★ Saved' : '☆ Save'}
                        </button>
                      </div>
                      <p className="title">{item.title ?? 'No title available'}</p>
                      <p className="meta">
                        GPA <strong>{item.avg_gpa ?? 'n/a'}</strong> · {item.difficulty ?? 'n/a'} difficulty
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
        </div>
      </section>

      <section className="section section-faq" ref={faqRef}>
        <div className="wrap faq-wrap reveal">
          <h2>FAQ</h2>
          <div className="faq-list">
            {faqs.map((item, index) => {
              const open = openFaq === index;
              return (
                <article className={`faq-item ${open ? 'open' : ''}`} key={item.q}>
                  <button className="faq-q" onClick={() => setOpenFaq(open ? -1 : index)}>
                    {item.q}
                    <span>{open ? '−' : '+'}</span>
                  </button>
                  <div className="faq-a">
                    <p>{item.a}</p>
                  </div>
                </article>
              );
            })}
          </div>
          <p className="footer-copy">© 2026 SaveMyGrade. All rights reserved.</p>
        </div>
      </section>
    </main>
  );
}

export default App;

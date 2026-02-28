import { useState } from 'react';
import './App.css';

const initialForm = {
  university: 'Simon Fraser University',
  query: 'I need an easier lower-division elective in science'
};

function App() {
  const [form, setForm] = useState(initialForm);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [results, setResults] = useState([]);

  const updateField = (event) => {
    const { name, value } = event.target;
    setForm((prev) => ({ ...prev, [name]: value }));
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
        body: JSON.stringify(form)
      });

      if (!response.ok) {
        throw new Error(`API returned ${response.status}`);
      }

      const payload = await response.json();
      setResults(payload.results ?? []);
    } catch (err) {
      setResults([]);
      setError(
        `${err.message}. Make sure your Flask API is running at http://localhost:5000.`
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="page">
      <section className="panel">
        <h1>SaveMyGrade</h1>
        <p className="subtitle">
          Find lower-stress courses using class averages and RateMyProfessor data.
        </p>

        <form onSubmit={handleSubmit} className="search-form">
          <label>
            University
            <input
              name="university"
              value={form.university}
              onChange={updateField}
              placeholder="Simon Fraser University"
              required
            />
          </label>

          <label>
            What do you need?
            <textarea
              name="query"
              value={form.query}
              onChange={updateField}
              rows="3"
              placeholder="Example: easiest CMPT electives with good prof ratings"
              required
            />
          </label>

          <button type="submit" disabled={loading}>
            {loading ? 'Searching...' : 'Get Recommendations'}
          </button>
        </form>

        {error ? <p className="status error">{error}</p> : null}

        <section className="results">
          <h2>Recommended Classes</h2>
          {results.length === 0 ? (
            <p className="status">No results yet. Submit a query to load suggestions.</p>
          ) : (
            <ul>
              {results.map((item, index) => (
                <li key={`${item.course_code}-${index}`}>
                  <h3>{item.course_code ?? 'Unknown Course'}</h3>
                  <p>{item.title ?? 'No title available'}</p>
                  <p>
                    Avg GPA: <strong>{item.avg_gpa ?? 'n/a'}</strong> | Difficulty:{' '}
                    <strong>{item.difficulty ?? 'n/a'}</strong>
                  </p>
                  <p>
                    Best-rated prof: <strong>{item.professor ?? 'n/a'}</strong> ({item.prof_rating ?? 'n/a'}/5)
                  </p>
                  {item.reason ? <p className="reason">Why: {item.reason}</p> : null}
                </li>
              ))}
            </ul>
          )}
        </section>
      </section>
    </main>
  );
}

export default App;

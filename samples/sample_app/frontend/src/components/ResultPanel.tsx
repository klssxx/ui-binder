interface Props {
  result: string;
  error: string;
}

/** Shows the generated idea or the error from the API. */
export default function ResultPanel({ result, error }: Props) {
  return (
    <section id="result_panel" className="result-panel">
      {error ? <p className="error">{error}</p> : <p className="result">{result}</p>}
    </section>
  );
}

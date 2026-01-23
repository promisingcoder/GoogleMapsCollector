import { useState, useCallback } from 'react'

function App() {
  const [curlInput, setCurlInput] = useState('')
  const [decoded, setDecoded] = useState(null)
  const [urlParams, setUrlParams] = useState({})
  const [pbParams, setPbParams] = useState([])
  const [originalPbParams, setOriginalPbParams] = useState([])
  const [headers, setHeaders] = useState({})
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [executing, setExecuting] = useState(false)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState('key')
  const [resultsTab, setResultsTab] = useState('businesses')
  const [pbFilter, setPbFilter] = useState('')

  const handleDecode = async () => {
    if (!curlInput.trim()) return

    setLoading(true)
    setError(null)
    setResults(null)

    try {
      const response = await fetch('/api/decode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ curl_command: curlInput }),
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to decode')
      }

      setDecoded(data.data)
      setUrlParams({ ...data.data.url_params })
      setPbParams(data.data.pb_params.map((p, idx) => ({ ...p, original_value: p.value, _idx: idx })))
      setOriginalPbParams(data.data.pb_params)
      setHeaders({ ...data.data.headers })
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleExecute = async () => {
    if (!decoded) return

    setExecuting(true)
    setError(null)

    try {
      const response = await fetch('/api/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          original_curl: curlInput,
          url_params: urlParams,
          pb_params: pbParams,
          headers: headers,
        }),
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to execute request')
      }

      setResults(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setExecuting(false)
    }
  }

  const handleUrlParamChange = (key, value) => {
    setUrlParams(prev => ({ ...prev, [key]: value }))
  }

  const handlePbParamChange = (index, value) => {
    setPbParams(prev => {
      const updated = [...prev]
      const param = updated[index]

      // Convert value based on type
      let converted = value
      if (param.type === 'i' || param.type === 'e') {
        converted = parseInt(value) || 0
      } else if (param.type === 'd' || param.type === 'f') {
        converted = parseFloat(value) || 0
      } else if (param.type === 'b') {
        converted = value === 'true' || value === '1'
      }

      updated[index] = { ...param, value: converted }
      return updated
    })
  }

  const downloadResults = () => {
    if (!results) return

    const blob = new Blob([JSON.stringify(results, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `google_maps_results_${Date.now()}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const filteredPbParams = pbParams.filter(p => {
    if (!pbFilter) return true
    const search = pbFilter.toLowerCase()
    return (
      p.path.toLowerCase().includes(search) ||
      String(p.value).toLowerCase().includes(search) ||
      (p.description || '').toLowerCase().includes(search)
    )
  })

  const keyParams = pbParams.filter(p =>
    ['!7i', '!8i', '!74i'].some(k => p.path === k) ||
    p.path.includes('!1s') && !p.path.includes('m') ||
    (p.path.includes('!4m') && p.path.includes('!1m') && ['!1d', '!2d', '!3d'].some(k => p.path.endsWith(k))) ||
    p.path.endsWith('!4f')
  )

  return (
    <div className="app">
      <header className="header">
        <h1>Google Maps PB Decoder</h1>
        <p>Decode, modify, and execute Google Maps search requests</p>
      </header>

      <div className="main-grid">
        {/* Input Panel */}
        <div className="panel">
          <div className="panel-header">
            <span>📥</span> Curl Input
          </div>
          <div className="panel-content input-section">
            <textarea
              value={curlInput}
              onChange={(e) => setCurlInput(e.target.value)}
              placeholder="Paste your curl command here..."
            />
            <div className="button-row">
              <button
                className="btn btn-primary"
                onClick={handleDecode}
                disabled={loading || !curlInput.trim()}
              >
                {loading ? (
                  <>
                    <span className="spinner"></span>
                    Decoding...
                  </>
                ) : (
                  <>🔍 Decode</>
                )}
              </button>
              <button
                className="btn btn-success"
                onClick={handleExecute}
                disabled={executing || !decoded}
              >
                {executing ? (
                  <>
                    <span className="spinner"></span>
                    Executing...
                  </>
                ) : (
                  <>▶ Run Request</>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Parameters Panel */}
        <div className="panel">
          <div className="panel-header">
            <span>⚙️</span> Parameters
          </div>
          <div className="panel-content params-section">
            {!decoded ? (
              <div className="empty-state">
                <span style={{ fontSize: '3rem' }}>📋</span>
                <p>Paste a curl command and click Decode to see parameters</p>
              </div>
            ) : (
              <>
                <div className="tabs">
                  <button
                    className={`tab ${activeTab === 'key' ? 'active' : ''}`}
                    onClick={() => setActiveTab('key')}
                  >
                    Key Values
                  </button>
                  <button
                    className={`tab ${activeTab === 'url' ? 'active' : ''}`}
                    onClick={() => setActiveTab('url')}
                  >
                    URL Params
                  </button>
                  <button
                    className={`tab ${activeTab === 'pb' ? 'active' : ''}`}
                    onClick={() => setActiveTab('pb')}
                  >
                    PB Params ({pbParams.length})
                  </button>
                </div>

                {activeTab === 'key' && (
                  <>
                    <div className="key-values">
                      {decoded.extracted.search_query && (
                        <div className="key-value-card">
                          <label>Search Query</label>
                          <div className="value">{decoded.extracted.search_query}</div>
                        </div>
                      )}
                      {decoded.extracted.latitude && (
                        <div className="key-value-card">
                          <label>Latitude</label>
                          <div className="value">{decoded.extracted.latitude?.toFixed(6)}</div>
                        </div>
                      )}
                      {decoded.extracted.longitude && (
                        <div className="key-value-card">
                          <label>Longitude</label>
                          <div className="value">{decoded.extracted.longitude?.toFixed(6)}</div>
                        </div>
                      )}
                      {decoded.extracted.results_count && (
                        <div className="key-value-card">
                          <label>Results Count (!7i)</label>
                          <div className="value">{decoded.extracted.results_count}</div>
                        </div>
                      )}
                      {decoded.extracted.offset !== null && (
                        <div className="key-value-card">
                          <label>Offset (!8i)</label>
                          <div className="value">{decoded.extracted.offset}</div>
                        </div>
                      )}
                      {decoded.extracted.max_radius && (
                        <div className="key-value-card">
                          <label>Max Radius (!74i)</label>
                          <div className="value">{decoded.extracted.max_radius?.toLocaleString()}m</div>
                        </div>
                      )}
                    </div>
                    <div className="param-group">
                      <div className="param-group-title">Edit Key Parameters</div>
                      {keyParams.map((param) => (
                          <div className="param-row" key={`key-${param._idx}`}>
                            <span className="param-key" title={param.description || param.path}>
                              {param.description || param.path}
                            </span>
                            <input
                              className={`param-input ${param.value !== param.original_value ? 'modified' : ''}`}
                              value={param.value}
                              onChange={(e) => handlePbParamChange(param._idx, e.target.value)}
                            />
                          </div>
                        ))}
                    </div>
                  </>
                )}

                {activeTab === 'url' && (
                  <div className="param-group">
                    {Object.entries(urlParams).map(([key, value]) => (
                      <div className="param-row" key={key}>
                        <span className="param-key">{key}</span>
                        <input
                          className="param-input"
                          value={value}
                          onChange={(e) => handleUrlParamChange(key, e.target.value)}
                        />
                      </div>
                    ))}
                  </div>
                )}

                {activeTab === 'pb' && (
                  <>
                    <input
                      className="filter-input"
                      type="text"
                      placeholder="Filter parameters (e.g., '7i', 'latitude')..."
                      value={pbFilter}
                      onChange={(e) => setPbFilter(e.target.value)}
                    />
                    <div className="param-group">
                      {filteredPbParams.map((param) => {
                        if (param.type === 'm') return null // Skip message containers
                        return (
                          <div className="param-row" key={`pb-${param._idx}`}>
                            <span className="param-key" title={param.description || ''}>
                              {param.path}
                            </span>
                            <input
                              className={`param-input ${param.value !== param.original_value ? 'modified' : ''}`}
                              value={param.value}
                              onChange={(e) => handlePbParamChange(param._idx, e.target.value)}
                            />
                          </div>
                        )
                      })}
                    </div>
                  </>
                )}
              </>
            )}
          </div>
        </div>

        {/* Results Panel */}
        {(results || error) && (
          <div className="panel results-panel">
            <div className="panel-header results-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span>📊</span> Results
              </div>
              {results && (
                <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                  <div className="results-stats">
                    {results.response?.business_count !== undefined && (
                      <span>{results.response.business_count} businesses found</span>
                    )}
                  </div>
                  <button className="btn btn-secondary" onClick={downloadResults}>
                    📥 Download JSON
                  </button>
                </div>
              )}
            </div>
            <div className="panel-content">
              {error && (
                <div className="error">
                  <strong>Error:</strong> {error}
                </div>
              )}

              {results && (
                <>
                  <div className="tabs">
                    <button
                      className={`tab ${resultsTab === 'businesses' ? 'active' : ''}`}
                      onClick={() => setResultsTab('businesses')}
                    >
                      Businesses
                    </button>
                    <button
                      className={`tab ${resultsTab === 'json' ? 'active' : ''}`}
                      onClick={() => setResultsTab('json')}
                    >
                      Raw JSON
                    </button>
                    <button
                      className={`tab ${resultsTab === 'request' ? 'active' : ''}`}
                      onClick={() => setResultsTab('request')}
                    >
                      Request Info
                    </button>
                  </div>

                  {resultsTab === 'businesses' && (
                    <div className="business-list">
                      {results.response?.businesses?.length > 0 ? (
                        results.response.businesses.map((biz, idx) => (
                          <div className="business-card" key={idx}>
                            <h4>{biz.name}</h4>
                            {biz.address && <p>📍 {biz.address}</p>}
                            {biz.phone && <p>📞 {biz.phone}</p>}
                            {biz.website && <p>🌐 {biz.website}</p>}
                            {biz.rating && <p>⭐ {biz.rating} ({biz.reviews} reviews)</p>}
                            {biz.coords && <p>📌 {biz.coords[0]}, {biz.coords[1]}</p>}
                          </div>
                        ))
                      ) : (
                        <div className="empty-state">
                          <p>No businesses extracted. Check Raw JSON tab for full response.</p>
                        </div>
                      )}
                    </div>
                  )}

                  {resultsTab === 'json' && (
                    <pre className="json-output">
                      {JSON.stringify(results.response, null, 2)}
                    </pre>
                  )}

                  {resultsTab === 'request' && (
                    <div>
                      <div className="param-group">
                        <div className="param-group-title">Request URL</div>
                        <pre className="json-output" style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                          {results.request?.url}
                        </pre>
                      </div>
                      <div className="param-group">
                        <div className="param-group-title">PB String</div>
                        <pre className="json-output" style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                          {results.request?.pb_string}
                        </pre>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default App

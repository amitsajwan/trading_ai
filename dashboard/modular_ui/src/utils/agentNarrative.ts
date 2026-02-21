const asString = (value: any): string => (value === undefined || value === null ? '' : String(value).trim())

const firstText = (...values: any[]): string => {
  for (const value of values) {
    const text = asString(value)
    if (text) return text
  }
  return ''
}

const parseJsonObject = (value: any): Record<string, any> | null => {
  const text = asString(value)
  if (!text || !text.startsWith('{')) return null
  try {
    const parsed = JSON.parse(text)
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : null
  } catch {
    return null
  }
}

export const getAgentExecutiveSummary = (row: any): string => {
  const details = (row?.details && typeof row.details === 'object') ? row.details : {}
  const parsedDetailsCommentary = parseJsonObject(details?.commentary)
  const parsedRowCommentary = parseJsonObject(row?.commentary)
  const directRowSummary = parsedRowCommentary ? '' : row?.executive_summary
  const directDetailsSummary = parsedDetailsCommentary ? '' : details?.executive_summary

  return firstText(
    parsedDetailsCommentary?.executive_summary,
    parsedRowCommentary?.executive_summary,
    directRowSummary,
    directDetailsSummary,
    details?.analysis_sections?.decision_rationale,
    row?.analysis_sections?.decision_rationale,
  )
}

export const getAgentCommentary = (row: any): string => {
  const details = (row?.details && typeof row.details === 'object') ? row.details : {}
  const parsedDetailsCommentary = parseJsonObject(details?.commentary)
  const parsedRowCommentary = parseJsonObject(row?.commentary)
  const directRowCommentary = parsedRowCommentary ? '' : row?.commentary
  const directDetailsCommentary = parsedDetailsCommentary ? '' : details?.commentary

  return firstText(
    parsedDetailsCommentary?.commentary,
    parsedRowCommentary?.commentary,
    directRowCommentary,
    directDetailsCommentary,
    details?.analysis_sections?.decision_rationale,
    row?.analysis_sections?.decision_rationale,
  )
}

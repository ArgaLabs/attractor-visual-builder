export default function Toast({ message, type }) {
  if (!message) return null
  return (
    <div className={`toast show${type ? ` ${type}` : ''}`}>
      {message}
    </div>
  )
}

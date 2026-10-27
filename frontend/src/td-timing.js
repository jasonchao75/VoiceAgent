/* Keep displayed uncertainty conservative; never turn a range into a midpoint. */
export function formatLatencyInterval(interval) {
  if(!interval || typeof interval.lower_ms!=='number' || typeof interval.upper_ms!=='number'
    || !Number.isFinite(interval.lower_ms) || !Number.isFinite(interval.upper_ms)
    || interval.lower_ms<0 || interval.upper_ms<interval.lower_ms) return null;
  const lower=Math.floor(interval.lower_ms*10)/10;
  const upper=Math.ceil(interval.upper_ms*10)/10;
  return `${lower}–${upper} ms`;
}

import type { OrderBookResponse } from "../types";
import CollapsiblePanel from "./CollapsiblePanel";

const fmt = (n: number) =>
  n >= 100 ? n.toLocaleString(undefined, { maximumFractionDigits: 2 }) : n.toFixed(5);

/**
 * Live order-book depth (crypto): buy/sell pressure from the imbalance of resting
 * size, the spread, and a compact ladder of the nearest levels.
 */
export default function OrderBook({ o }: { o: OrderBookResponse }) {
  const b = o.book;
  if (!b) return null;
  const asks = b.asks.slice(0, 6).reverse(); // highest ask on top
  const bids = b.bids.slice(0, 6);
  const maxQ = Math.max(...[...b.bids.slice(0, 6), ...b.asks.slice(0, 6)].map((l) => l.qty), 1e-9);
  const bidPct = b.imbalance_pct;
  const askPct = 100 - b.imbalance_pct;
  return (
    <CollapsiblePanel title="Order Book"
      right={<span className={`ob-tag ${bidPct >= 50 ? "buy" : "sell"}`}>{bidPct >= 50 ? "Buy" : "Sell"} pressure</span>}>
      <div className="ob-imbar">
        <span className="ob-bidbar" style={{ width: `${bidPct}%` }}>{Math.round(bidPct)}%</span>
        <span className="ob-askbar" style={{ width: `${askPct}%` }}>{Math.round(askPct)}%</span>
      </div>
      <div className="ob-ladder">
        {asks.map((l, i) => (
          <div key={`a${i}`} className="ob-l ask">
            <span className="ob-q" style={{ width: `${(l.qty / maxQ) * 100}%` }} />
            <span className="ob-price">{fmt(l.price)}</span>
            <span className="ob-qty">{l.qty}</span>
          </div>
        ))}
        <div className="ob-mid">spread {b.spread_pct}% · mid {fmt(b.mid)}</div>
        {bids.map((l, i) => (
          <div key={`b${i}`} className="ob-l bid">
            <span className="ob-q" style={{ width: `${(l.qty / maxQ) * 100}%` }} />
            <span className="ob-price">{fmt(l.price)}</span>
            <span className="ob-qty">{l.qty}</span>
          </div>
        ))}
      </div>
    </CollapsiblePanel>
  );
}

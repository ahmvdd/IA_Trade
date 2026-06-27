import { Component, OnInit, signal, computed, inject } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { ApiService } from '../services/api.service';
import { PaperTradeRecord } from '../models/types';

const STARTING_CAPITAL = 10_000;

@Component({
  selector: 'app-paper-trading',
  imports: [DecimalPipe],
  templateUrl: './paper-trading.component.html',
  styleUrl: './paper-trading.component.css',
})
export class PaperTradingComponent implements OnInit {
  private api = inject(ApiService);

  trades  = signal<PaperTradeRecord[]>([]);
  loading = signal(false);
  error   = signal<string | null>(null);

  // ── Summary stats derived from the trades list ────────────────────────────

  totalTrades = computed(() => this.trades().length);

  winRate = computed(() => {
    const t = this.trades();
    if (t.length === 0) return 0;
    return (t.filter(r => r.Result === 'WIN').length / t.length) * 100;
  });

  lossRate = computed(() => this.totalTrades() === 0 ? 0 : 100 - this.winRate());

  totalPnl = computed(() =>
    this.trades().reduce((sum, r) => sum + r['PnL $'], 0)
  );

  currentCapital = computed(() => STARTING_CAPITAL + this.totalPnl());

  avgWin = computed(() => {
    const wins = this.trades().filter(r => r.Result === 'WIN');
    if (wins.length === 0) return 0;
    return wins.reduce((sum, r) => sum + r['PnL $'], 0) / wins.length;
  });

  avgLoss = computed(() => {
    const losses = this.trades().filter(r => r.Result === 'LOSS');
    if (losses.length === 0) return 0;
    return losses.reduce((sum, r) => sum + r['PnL $'], 0) / losses.length;
  });

  avgPnl = computed(() => {
    const t = this.trades();
    if (t.length === 0) return 0;
    return t.reduce((sum, r) => sum + r['PnL $'], 0) / t.length;
  });

  // ── Financial metrics (BNP-level) ─────────────────────────────────────────

  sharpeRatio = computed(() => {
    const t = this.trades();
    if (t.length < 2) return null;
    const returns = t.map(r => r['PnL %'] / 100);
    const mean    = returns.reduce((a, b) => a + b, 0) / returns.length;
    const variance = returns.reduce((sum, r) => sum + (r - mean) ** 2, 0) / (returns.length - 1);
    const std     = Math.sqrt(variance);
    if (std === 0) return null;
    const dailyRf = 0.05 / 252;
    return ((mean - dailyRf) / std) * Math.sqrt(252);
  });

  maxDrawdown = computed(() => {
    const t = this.trades();
    if (t.length === 0) return 0;
    let peak = 0, maxDd = 0, cumulative = 0;
    for (const trade of t) {
      cumulative += trade['PnL $'];
      if (cumulative > peak) peak = cumulative;
      const dd = cumulative - peak;
      if (dd < maxDd) maxDd = dd;
    }
    return maxDd;
  });

  ngOnInit(): void {
    this.loading.set(true);

    this.api.getPaperTrades().subscribe({
      next: (res) => {
        this.trades.set(res.trades);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Could not reach the Flask API — is it running on port 5001?');
        this.loading.set(false);
      },
    });
  }
}

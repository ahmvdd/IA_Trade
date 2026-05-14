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

  totalPnl = computed(() =>
    this.trades().reduce((sum, r) => sum + r['PnL $'], 0)
  );

  currentCapital = computed(() => STARTING_CAPITAL + this.totalPnl());

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

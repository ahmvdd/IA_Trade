import { Component, OnInit, computed, signal, inject } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { BaseChartDirective } from 'ng2-charts';
import type { ChartData, ChartOptions } from 'chart.js';
import { ApiService } from '../services/api.service';
import { PriceRecord } from '../models/types';

@Component({
  selector: 'app-prices',
  imports: [DecimalPipe, BaseChartDirective],
  templateUrl: './prices.component.html',
  styleUrl: './prices.component.css',
})
export class PricesComponent implements OnInit {
  private api = inject(ApiService);

  readonly assets = [
    { label: 'GOLD    / USD', ticker: 'GC=F'    },
    { label: 'OIL     / USD', ticker: 'CL=F'    },
    { label: 'BITCOIN / USD', ticker: 'BTC-USD'  },
    { label: 'APPLE   / USD', ticker: 'AAPL'     },
    { label: 'S&P 500       ', ticker: '^GSPC'   },
  ];

  readonly displayedColumns = ['date', 'close', 'rsi', 'sma20', 'sma50', 'signal'];

  selectedTicker = signal('GC=F');
  allRows        = signal<PriceRecord[]>([]);  // 30 rows → chart
  rows           = signal<PriceRecord[]>([]);  // last 10 → table
  loading        = signal(false);
  error          = signal<string | null>(null);

  // Animated values for the count-up effect in the top bar
  animatedClose = signal(0);
  animatedRsi   = signal(0);

  latestRow = computed(() => {
    const r = this.rows();
    return r.length > 0 ? r[r.length - 1] : null;
  });

  // ── Chart.js — Bloomberg terminal style ──────────────────────────────────

  readonly chartOptions: ChartOptions<'line'> = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: {
        labels: {
          color: '#444444',
          font: { size: 10, family: "'IBM Plex Mono', monospace" },
          usePointStyle: true,
          pointStyleWidth: 8,
          padding: 20,
        },
      },
      tooltip: {
        backgroundColor: '#0f0f0f',
        titleColor: '#e0e0e0',
        bodyColor: '#666666',
        borderColor: '#1e1e1e',
        borderWidth: 1,
        padding: 10,
        titleFont: { family: "'IBM Plex Mono', monospace", size: 11 },
        bodyFont: { family: "'IBM Plex Mono', monospace", size: 11 },
      },
    },
    scales: {
      x: {
        ticks: {
          color: '#444444',
          maxRotation: 0,
          maxTicksLimit: 8,
          font: { size: 9, family: "'IBM Plex Mono', monospace" },
        },
        grid:   { color: 'rgba(255,255,255,0.02)' },
        border: { color: '#1e1e1e' },
      },
      y: {
        position: 'right',
        ticks: {
          color: '#444444',
          font: { size: 9, family: "'IBM Plex Mono', monospace" },
        },
        grid:   { color: 'rgba(255,255,255,0.02)' },
        border: { color: '#1e1e1e' },
      },
    },
  };

  chartData = computed<ChartData<'line'>>(() => {
    const data = this.allRows();
    return {
      labels: data.map(r => r.date),
      datasets: [
        {
          label: 'CLOSE',
          data: data.map(r => r.Close),
          borderColor: '#e0e0e0',
          borderWidth: 1.5,
          pointRadius: 0,
          pointHoverRadius: 3,
          tension: 0.2,
          fill: false,
          order: 1,
        },
        {
          label: 'SMA 20',
          data: data.map(r => r.SMA_20),
          borderColor: '#00d4aa',
          borderWidth: 1,
          pointRadius: 0,
          pointHoverRadius: 3,
          tension: 0.2,
          fill: false,
          order: 2,
        },
        {
          label: 'SMA 50',
          data: data.map(r => r.SMA_50),
          borderColor: '#f0a030',
          borderWidth: 1,
          pointRadius: 0,
          pointHoverRadius: 3,
          tension: 0.2,
          fill: false,
          order: 3,
        },
        {
          label: 'BUY',
          data: data.map(r => (r.Signal === 'BUY' ? r.Close : null)),
          showLine: false,
          pointRadius: 6,
          pointHoverRadius: 8,
          pointBackgroundColor: '#00d4aa',
          pointBorderColor: '#00d4aa',
          borderColor: 'transparent',
          order: 0,
        },
        {
          label: 'SELL',
          data: data.map(r => (r.Signal === 'SELL' ? r.Close : null)),
          showLine: false,
          pointRadius: 6,
          pointHoverRadius: 8,
          pointBackgroundColor: '#ff4444',
          pointBorderColor: '#ff4444',
          borderColor: 'transparent',
          order: 0,
        },
      ],
    };
  });

  ngOnInit(): void {
    this.load();
  }

  onAssetChange(event: Event): void {
    const ticker = (event.target as HTMLSelectElement).value;
    const asset  = this.assets.find(a => a.ticker === ticker);
    this.selectedTicker.set(ticker);
    // strip the label override — we only need the ticker for API calls
    void asset;
    this.load();
  }

  rsiClass(rsi: number | null): string {
    if (rsi === null) return '';
    if (rsi < 30)    return 'sig-buy';
    if (rsi > 70)    return 'sig-sell';
    return '';
  }

  // ── Count-up animation ────────────────────────────────────────────────────

  private countUpId = 0;

  private countUp(target: number, setter: (v: number) => void): void {
    const id       = ++this.countUpId;
    const duration = 700;
    const start    = performance.now();

    const tick = (now: number): void => {
      if (id !== this.countUpId) return;       // cancelled by a newer call
      const t      = Math.min((now - start) / duration, 1);
      const eased  = 1 - Math.pow(1 - t, 3);  // ease-out cubic
      setter(target * eased);
      if (t < 1) requestAnimationFrame(tick);
      else setter(target);
    };

    requestAnimationFrame(tick);
  }

  private load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.allRows.set([]);
    this.rows.set([]);

    this.api.getMlSignals(this.selectedTicker()).subscribe({
      next: (res) => {
        this.allRows.set(res.data);
        this.rows.set(res.data.slice(-10));

        const latest = res.data[res.data.length - 1];
        if (latest) {
          this.animatedClose.set(0);
          this.animatedRsi.set(0);
          this.countUp(latest.Close, v => this.animatedClose.set(v));
          if (latest.RSI !== null) {
            this.countUp(latest.RSI, v => this.animatedRsi.set(v));
          }
        }

        this.loading.set(false);
      },
      error: () => {
        this.error.set('Could not reach the Flask API — is it running on port 5001?');
        this.loading.set(false);
      },
    });
  }
}

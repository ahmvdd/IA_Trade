import { Component, OnInit, signal, inject } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { ApiService } from '../services/api.service';
import { TradeRecord } from '../models/types';

@Component({
  selector: 'app-trades',
  imports: [DecimalPipe],
  templateUrl: './trades.component.html',
  styleUrl: './trades.component.css',
})
export class TradesComponent implements OnInit {
  private api = inject(ApiService);

  trades  = signal<TradeRecord[]>([]);
  loading = signal(false);
  error   = signal<string | null>(null);

  ngOnInit(): void {
    this.loading.set(true);

    this.api.getTrades().subscribe({
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

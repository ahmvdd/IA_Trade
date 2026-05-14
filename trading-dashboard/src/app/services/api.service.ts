import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { PricesResponse, TradesResponse, PaperTradesResponse } from '../models/types';

const API_BASE = 'http://localhost:5001';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private http = inject(HttpClient);

  getPrices(ticker: string): Observable<PricesResponse> {
    return this.http.get<PricesResponse>(`${API_BASE}/prices/${ticker}`);
  }

  getTrades(): Observable<TradesResponse> {
    return this.http.get<TradesResponse>(`${API_BASE}/trades`);
  }

  getPaperTrades(): Observable<PaperTradesResponse> {
    return this.http.get<PaperTradesResponse>(`${API_BASE}/paper-trades`);
  }
}

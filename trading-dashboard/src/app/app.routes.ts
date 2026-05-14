import { Routes } from '@angular/router';
import { PricesComponent } from './prices/prices.component';
import { TradesComponent } from './trades/trades.component';
import { PaperTradingComponent } from './paper-trading/paper-trading.component';

export const routes: Routes = [
  { path: '',             redirectTo: 'prices', pathMatch: 'full' },
  { path: 'prices',       component: PricesComponent },
  { path: 'trades',       component: TradesComponent },
  { path: 'paper-trading', component: PaperTradingComponent },
];

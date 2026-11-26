import { Routes } from '@angular/router';
import { authGuard, sysadminGuard } from './core/guards/auth.guard';
import { LoginComponent } from './features/auth/login/login.component';
import { ShellComponent } from './layout/shell/shell.component';
import { OverviewComponent } from './features/overview/overview.component';
import { DriveListComponent } from './features/drives/drive-list/drive-list.component';
import { DriveDetailComponent } from './features/drives/drive-detail/drive-detail.component';
import { UploadComponent } from './features/upload/upload.component';
import { ValidationComponent } from './features/validation/validation.component';
import { PredictionsComponent } from './features/predictions/predictions.component';
import { MlModelsComponent } from './features/ml-models/ml-models.component';
import { UsersComponent } from './features/users/users.component';
import { ProfileComponent } from './features/profile/profile.component';

export const routes: Routes = [
  { path: 'login', component: LoginComponent },
  {
    path: '',
    component: ShellComponent,
    canActivate: [authGuard],
    children: [
      { path: '', redirectTo: 'overview', pathMatch: 'full' },
      { path: 'overview', component: OverviewComponent },
      { path: 'drives', component: DriveListComponent },
      { path: 'drives/:id', component: DriveDetailComponent },
      { path: 'upload', component: UploadComponent },
      { path: 'validation', component: ValidationComponent },
      { path: 'predictions', component: PredictionsComponent },
      { path: 'models', component: MlModelsComponent },
      { path: 'users', component: UsersComponent, canActivate: [sysadminGuard] },
      { path: 'profile', component: ProfileComponent },
    ],
  },
  { path: '**', redirectTo: 'overview' },
];

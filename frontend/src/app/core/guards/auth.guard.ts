import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { map } from 'rxjs';
import { AuthService } from '../services/auth.service';
import { Role } from '../models/auth.models';

export const authGuard: CanActivateFn = (route, state) => {
  const authService = inject(AuthService);
  const router = inject(Router);

  if (!authService.getAccessToken()) {
    return router.createUrlTree(['/login'], { queryParams: { returnUrl: state.url } });
  }

  return authService.ensureProfileLoaded().pipe(
    map((user) => user ? true : router.createUrlTree(['/login'], { queryParams: { returnUrl: state.url } })),
  );
};

function roleGuard(allowedRoles: Role[]): CanActivateFn {
  return () => {
    const authService = inject(AuthService);
    const router = inject(Router);

    return authService.ensureProfileLoaded().pipe(
      map((user) => {
        if (user && allowedRoles.includes(user.role)) return true;
        return router.createUrlTree(['/overview']);
      }),
    );
  };
}

export const sysadminGuard: CanActivateFn = roleGuard(['SYSADMIN']);
export const itProOrSysadminGuard: CanActivateFn = roleGuard(['IT_PRO', 'SYSADMIN']);

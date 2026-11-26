import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, switchMap, throwError } from 'rxjs';
import { AuthService } from '../services/auth.service';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const authService = inject(AuthService);
  const token = authService.getAccessToken();

  let authReq = req;
  const isTokenEndpoint = req.url.includes('/auth/login/') || req.url.includes('/auth/refresh/');
  const isLogoutEndpoint = req.url.includes('/auth/logout/');

  if (token && !isTokenEndpoint) {
    authReq = req.clone({
      setHeaders: {
        Authorization: `Bearer ${token}`,
      },
    });
  }

  return next(authReq).pipe(
    catchError((error: HttpErrorResponse) => {
      if (error.status === 401 && !isTokenEndpoint && !isLogoutEndpoint) {
        return authService.refreshToken().pipe(
          switchMap((newToken) => {
            const retryReq = req.clone({
              setHeaders: {
                Authorization: `Bearer ${newToken.access}`,
              },
            });
            return next(retryReq);
          }),
          catchError((refreshErr) => {
            authService.logout();
            return throwError(() => refreshErr);
          })
        );
      }
      return throwError(() => error);
    })
  );
};

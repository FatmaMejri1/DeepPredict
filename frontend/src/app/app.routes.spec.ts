import { routes } from './app.routes';
import { sysadminGuard } from './core/guards/auth.guard';

describe('audit log route authorization', () => {
  it('protects /audit-logs with the existing SYSADMIN guard', () => {
    const shellRoute = routes.find((route) => route.path === '');
    const auditRoute = shellRoute?.children?.find((route) => route.path === 'audit-logs');
    expect(auditRoute).toBeDefined();
    expect(auditRoute?.canActivate).toContain(sysadminGuard);
  });
});

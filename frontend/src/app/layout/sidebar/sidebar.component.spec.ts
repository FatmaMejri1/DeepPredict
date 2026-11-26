import { signal } from '@angular/core';
import { provideRouter } from '@angular/router';
import { TestBed } from '@angular/core/testing';
import { AuthService } from '../../core/services/auth.service';
import { SidebarComponent } from './sidebar.component';

describe('Sidebar audit navigation', () => {
  async function createSidebar(role: string) {
    await TestBed.configureTestingModule({
      imports: [SidebarComponent],
      providers: [
        provideRouter([]),
        {
          provide: AuthService,
          useValue: {
            currentUser: signal({ username: 'test-user', role }),
            isSysAdmin: signal(role === 'SYSADMIN'),
            isOperator: signal(role === 'OPERATOR'),
            isITProOrSysAdmin: signal(role !== 'OPERATOR'),
            logout: vi.fn(),
          },
        },
      ],
    }).compileComponents();
    const fixture = TestBed.createComponent(SidebarComponent);
    fixture.detectChanges();
    return fixture;
  }

  it('shows audit navigation only for SYSADMIN', async () => {
    const admin = await createSidebar('SYSADMIN');
    expect(admin.nativeElement.querySelector('a[routerLink="/audit-logs"]')).not.toBeNull();
    TestBed.resetTestingModule();
    const itPro = await createSidebar('IT_PRO');
    expect(itPro.nativeElement.querySelector('a[routerLink="/audit-logs"]')).toBeNull();
    TestBed.resetTestingModule();
    const operator = await createSidebar('OPERATOR');
    expect(operator.nativeElement.querySelector('a[routerLink="/audit-logs"]')).toBeNull();
  });
});

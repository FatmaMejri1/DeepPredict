import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { UserService } from './user.service';

describe('UserService', () => {
  let service: UserService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(UserService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('lists users from the existing users endpoint', () => {
    let usernames: string[] = [];
    service.getUsers().subscribe((users) => { usernames = users.map((user) => user.username); });

    http.expectOne('/api/users/').flush({ results: [
      { id: '8debe1a7-c947-4a88-a915-226eaf7db895', username: 'operator', role: 'OPERATOR' },
    ] });

    expect(usernames).toEqual(['operator']);
  });

  it('edits a user using the UUID from Django', () => {
    const id = '8debe1a7-c947-4a88-a915-226eaf7db895';
    service.updateUser(id, { role: 'IT_PRO' }).subscribe();

    const request = http.expectOne(`/api/users/${id}/`);
    expect(request.request.method).toBe('PATCH');
    expect(request.request.body).toEqual({ role: 'IT_PRO' });
    request.flush({ id, username: 'operator', role: 'IT_PRO' });
  });

  it('resets a user password using Django’s hyphenated action route', () => {
    const id = '8debe1a7-c947-4a88-a915-226eaf7db895';
    service.setPassword(id, 'temporary-test-password').subscribe();

    const request = http.expectOne(`/api/users/${id}/set-password/`);
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ password: 'temporary-test-password' });
    request.flush({ detail: 'Password updated.' });
  });
});

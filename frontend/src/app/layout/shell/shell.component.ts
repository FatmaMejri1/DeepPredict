import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { SidebarComponent } from '../sidebar/sidebar.component';
import { HeaderComponent } from '../header/header.component';

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [CommonModule, RouterModule, SidebarComponent, HeaderComponent],
  template: `
    <div class="app-layout">
      <app-sidebar [class.collapsed]="sidebarCollapsed"></app-sidebar>
      <div class="main-wrapper">
        <app-header (toggleSidebar)="onToggleSidebar()"></app-header>
        <main class="content-area">
          <router-outlet></router-outlet>
        </main>
      </div>
    </div>
  `,
  styles: [`
    .app-layout {
      display: flex;
      height: 100vh;
      overflow: hidden;
      background: var(--bg-app);
    }

    .main-wrapper {
      flex: 1;
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
    }

    .content-area {
      flex: 1;
      overflow-y: auto;
      padding: 1.5rem 2rem;
    }
  `],
})
export class ShellComponent {
  sidebarCollapsed = false;

  onToggleSidebar(): void {
    this.sidebarCollapsed = !this.sidebarCollapsed;
  }
}

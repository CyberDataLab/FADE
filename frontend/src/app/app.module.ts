import { NgModule } from '@angular/core';
import { BrowserModule } from '@angular/platform-browser';
import { FormsModule } from '@angular/forms'
import { BrowserAnimationsModule } from '@angular/platform-browser/animations';
import { HttpClientModule, provideHttpClient, withFetch } from '@angular/common/http';
import { AppRoutingModule } from './app-routing.module';
import { AppComponent } from './app.component';
import { AuthenticationService } from './Core/services/authentication.service';
import { UserService } from './User/user.service';
import { LoginComponent } from './Authentication/login/login.component';
import { DragDropModule } from '@angular/cdk/drag-drop';
import { NewScenarioComponent } from './Windows/scenarios/new-scenario/new-scenario.component';
import { ThemeToggleComponent } from './Theme/theme-toggle/theme-toggle.component';

@NgModule({
  declarations: [
    AppComponent,
    LoginComponent,
    NewScenarioComponent,
    ThemeToggleComponent
  ],
  imports: [
    BrowserModule,
    DragDropModule,
    AppRoutingModule,
    FormsModule,
    BrowserAnimationsModule,
    HttpClientModule
  ],
  providers: [
    provideHttpClient(withFetch()),
    AuthenticationService,
    UserService
  ],
  bootstrap: [AppComponent]
})
export class AppModule { }

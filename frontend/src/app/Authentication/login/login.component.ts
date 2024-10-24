import { Component, OnInit } from '@angular/core'
import { Router} from '@angular/router';
import { first } from 'rxjs/operators';
import { CommonModule } from '@angular/common'; // Importa CommonModule
import { FormsModule } from '@angular/forms'; // Si usas formularios en el template
import { RouterModule } from '@angular/router';
import { UserLogin } from '../../DTOs/UserLogin';
import { AuthenticationService } from '../authentication.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule,
    FormsModule,
    RouterModule
  ],
  templateUrl: './login.component.html',
  styleUrl: './login.component.css'
})
export class LoginComponent implements OnInit {

  userLoginDTO: UserLogin = {
    username: '',
    password: ''
  };

  usernameError: boolean;
  passwordError: boolean;

  constructor(private authenticationService: AuthenticationService, private router: Router) { 
    this.usernameError = false;
    this.passwordError = false;
  }

  ngOnInit(): void {
    if(this.authenticationService.valorUsuarioActual != null){
      this.router.navigate(["/dashboard"]);
    }
  }

  keyDownFunction(event: KeyboardEvent): void{
    if (event.key === 'Enter'){
      this.login();
    }
  }

  login() {
    if (this.userLoginDTO.username !== '' && this.userLoginDTO.password !== '') {
      const loginObs = this.authenticationService.login(this.userLoginDTO);

      if (loginObs) {
        loginObs.pipe(first())
          .subscribe(
            data => {
              this.router.navigate(["/dashboard"]);
            },
            error => {
              // If the login observable is null or an error occurs, you can handle it like this
              console.error('Login failed', error);
              alert('Wrong user or password.');
            }
          );
      } else {
        // User is already logged in, redirect them to the info page.
        alert('You are already logged in.');
        this.router.navigate(["/dashboard"]);
      }
    } else {
      if (this.userLoginDTO.username === '') {
        this.usernameError = true;
      }
      if (this.userLoginDTO.password === '') {
        this.passwordError = true;
      }
    }
  }
   
}

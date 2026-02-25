package com.example.navegation.navigation

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.example.navegation.views.ConfirmationScreen
import com.example.navegation.views.DetailScreen
import com.example.navegation.views.HomeScreen

@Composable
fun AppNavigation(modifier: Modifier = Modifier) {
    val navController = rememberNavController()

    NavHost(
        navController = navController,
        startDestination = "home",
        modifier = modifier
    ) {
        composable("home") {
            HomeScreen(
                onItemClick = { name ->
                    navController.navigate("detail/$name")
                }
            )
        }

        composable(
            route = "detail/{name}",
            arguments = listOf(navArgument("name") { type = NavType.StringType })
        ) { backStackEntry ->
            val name = backStackEntry.arguments?.getString("name") ?: ""
            DetailScreen(
                name = name,
                onNavigateToConfirmation = {
                    navController.navigate("confirmation")
                },
                onBack = {
                    navController.popBackStack()
                }
            )
        }

        composable("confirmation") {
            ConfirmationScreen(
                onBackToHome = {
                    navController.popBackStack("home", inclusive = false)
                }
            )
        }
    }
}